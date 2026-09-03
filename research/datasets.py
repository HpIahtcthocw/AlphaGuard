"""Point-in-time OHLCV dataset contract and validation helpers."""

from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
from typing import Optional, Union

import pandas as pd


REQUIRED_COLUMNS = ("date", "symbol", "open", "high", "low", "close", "volume")
OPTIONAL_COLUMNS = ("adjusted_close", "currency", "market")
DATASET_KINDS = {"REAL_MARKET_DATA", "DELAYED", "SNAPSHOT", "SYNTHETIC"}


def validate_ohlcv_frame(frame: pd.DataFrame, dataset_kind: str = "REAL_MARKET_DATA") -> dict[str, object]:
    """Return a deterministic, serializable quality report for OHLCV rows."""
    errors: list[str] = []
    warnings: list[str] = []
    kind = dataset_kind.strip().upper()
    if kind not in DATASET_KINDS:
        errors.append(f"dataset_kind must be one of {sorted(DATASET_KINDS)}")
    missing = [column for column in REQUIRED_COLUMNS if column not in frame.columns]
    if missing:
        errors.append(f"missing required columns: {', '.join(missing)}")
        return _report(frame, kind, errors, warnings)
    data = frame.copy()
    parsed_dates = pd.to_datetime(data["date"], errors="coerce")
    if parsed_dates.isna().any():
        errors.append("invalid date values detected")
    data["date"] = parsed_dates
    data["symbol"] = data["symbol"].astype(str).str.strip().str.upper()
    if (data["symbol"] == "").any() or data["symbol"].isna().any():
        errors.append("symbol cannot be empty")
    if data[["date", "symbol"]].duplicated().any():
        errors.append("duplicate symbol/date rows detected")
    if not data[["date", "symbol"]].sort_values(["date", "symbol"]).equals(data[["date", "symbol"]]):
        warnings.append("rows are not sorted by date and symbol")
    numeric = ["open", "high", "low", "close", "volume"]
    for column in numeric:
        data[column] = pd.to_numeric(data[column], errors="coerce")
    if data[numeric].isna().any().any():
        errors.append("non-numeric or missing OHLCV values detected")
    if (data[["open", "high", "low", "close"]] <= 0).any().any():
        errors.append("OHLC prices must be positive")
    if (data["volume"] < 0).any():
        errors.append("volume cannot be negative")
    valid = data.dropna(subset=numeric + ["date"])
    if not valid.empty:
        bad_ohlc = (valid["high"] < valid[["open", "close"]].max(axis=1)) | (valid["low"] > valid[["open", "close"]].min(axis=1)) | (valid["low"] > valid["high"])
        if bad_ohlc.any():
            errors.append("OHLC relationship invalid: high/low do not contain open and close")
        jumps = valid.sort_values(["symbol", "date"]).groupby("symbol")["close"].pct_change(fill_method=None).abs()
        extreme = int((jumps > 0.30).sum())
        if extreme:
            warnings.append(f"{extreme} close-to-close moves exceed 30%; review corporate actions or bad ticks")
    if "adjusted_close" not in data.columns:
        warnings.append("adjusted_close is absent; split/dividend-adjusted research is not guaranteed")
    elif pd.to_numeric(data["adjusted_close"], errors="coerce").isna().any():
        warnings.append("adjusted_close contains missing or non-numeric values")
    return _report(data, kind, errors, warnings)


def load_ohlcv_csv(source: Union[str, Path, io.StringIO], dataset_kind: str = "REAL_MARKET_DATA") -> tuple[pd.DataFrame, dict[str, object]]:
    """Load a CSV and validate it without silently repairing values."""
    frame = pd.read_csv(source)
    report = validate_ohlcv_frame(frame, dataset_kind)
    if report["errors"]:
        raise ValueError("; ".join(report["errors"]))
    frame = frame.copy()
    frame["date"] = pd.to_datetime(frame["date"])
    frame["symbol"] = frame["symbol"].astype(str).str.strip().str.upper()
    frame = frame.sort_values(["date", "symbol"]).reset_index(drop=True)
    report["data_fingerprint"] = fingerprint_ohlcv(frame)
    return frame, report


def fingerprint_ohlcv(frame: pd.DataFrame) -> str:
    canonical = frame.copy()
    canonical = canonical.reindex(sorted(canonical.columns), axis=1)
    canonical = canonical.sort_values([column for column in ("date", "symbol") if column in canonical.columns])
    payload = canonical.where(pd.notna(canonical), None).to_dict(orient="records")
    return hashlib.sha256(json.dumps(payload, default=str, separators=(",", ":")).encode("utf-8")).hexdigest()


def _report(frame: pd.DataFrame, kind: str, errors: list[str], warnings: list[str]) -> dict[str, object]:
    dates = pd.to_datetime(frame["date"], errors="coerce") if "date" in frame.columns else pd.Series(dtype="datetime64[ns]")
    symbols = sorted({str(item).upper() for item in frame.get("symbol", pd.Series(dtype=str)).dropna()})
    return {
        "dataset_kind": kind,
        "errors": sorted(set(errors)),
        "warnings": sorted(set(warnings)),
        "rows": int(len(frame)),
        "symbols": symbols,
        "start": dates.min().date().isoformat() if dates.notna().any() else None,
        "end": dates.max().date().isoformat() if dates.notna().any() else None,
        "required_columns": list(REQUIRED_COLUMNS),
        "optional_columns": list(OPTIONAL_COLUMNS),
    }
