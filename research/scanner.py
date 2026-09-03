"""Cross-sectional scanning and research portfolio construction for S-003."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping, Optional

import pandas as pd

from strategies.regime_breakout import BreakoutConfig, evaluate_breakout_signal


@dataclass(frozen=True)
class ScannerConfig:
    max_long_positions: int = 5
    max_short_positions: int = 5
    max_single_weight: float = 0.20
    long_exposure_bull: float = 0.80
    short_exposure_bear: float = 0.50
    min_long_score: float = 0.50
    min_short_score: float = 0.50


def scan_universe(
    universe: Mapping[str, pd.DataFrame],
    benchmark_close: Optional[pd.Series],
    market: str,
    metadata: Optional[Mapping[str, Mapping[str, object]]] = None,
    breakout_config: Optional[BreakoutConfig] = None,
    scanner_config: Optional[ScannerConfig] = None,
) -> dict[str, Any]:
    if not universe:
        raise ValueError("universe cannot be empty")
    scanner_config = scanner_config or ScannerConfig()
    if scanner_config.max_long_positions < 1 or scanner_config.max_short_positions < 0:
        raise ValueError("invalid position limits")
    if not 0 < scanner_config.max_single_weight <= 1:
        raise ValueError("max_single_weight must be between 0 and 1")
    if not 0 <= scanner_config.long_exposure_bull <= 1 or not 0 <= scanner_config.short_exposure_bear <= 1:
        raise ValueError("exposures must be between 0 and 1")
    metadata = metadata or {}
    signals: list[dict[str, Any]] = []
    for symbol, bars in universe.items():
        info = metadata.get(symbol, {})
        signal = evaluate_breakout_signal(
            bars,
            benchmark_close,
            market,
            symbol,
            shortable=bool(info.get("shortable", False)),
            borrow_cost_bps=_optional_float(info.get("borrow_cost_bps")),
            config=breakout_config,
        )
        signal["metadata"] = {"name": str(info.get("name") or symbol), "sector": info.get("sector"), "shortable": bool(info.get("shortable", False)), "borrow_cost_bps": signal["borrow_cost_bps"]}
        signals.append(signal)
    regime = _universe_regime(signals)
    longs = sorted((item for item in signals if item["direction"] == "LONG" and item["long_score"] >= scanner_config.min_long_score), key=lambda item: item["long_score"], reverse=True)[: scanner_config.max_long_positions]
    shorts = sorted((item for item in signals if item["direction"] == "SHORT" and item["short_score"] >= scanner_config.min_short_score), key=lambda item: item["short_score"], reverse=True)[: scanner_config.max_short_positions]
    long_budget = scanner_config.long_exposure_bull if regime == "BULL" else 0.0
    short_budget = scanner_config.short_exposure_bear if regime == "BEAR" else 0.0
    weights = _allocate(longs, long_budget, scanner_config.max_single_weight, "LONG")
    weights.update(_allocate([item for item in shorts if item["short_executable"]], short_budget, scanner_config.max_single_weight, "SHORT"))
    for item in signals:
        item["portfolio_weight"] = weights.get(item["symbol"], 0.0)
        item["portfolio_included"] = item["symbol"] in weights
        if item["direction"] == "SHORT" and not item["short_executable"]:
            item["portfolio_exclusion_reason"] = "Short signal is valid but lacks borrowable-shares confirmation"
    gross = sum(abs(value) for value in weights.values())
    net = sum(weights.values())
    return {
        "strategy_id": "S-003",
        "strategy_version": "0.1.0",
        "market": market.upper(),
        "as_of": max(str(item["as_of"]) for item in signals),
        "market_regime": regime,
        "config": {"breakout": asdict(breakout_config or BreakoutConfig()), "scanner": asdict(scanner_config)},
        "signals": sorted(signals, key=lambda item: max(item["long_score"], item["short_score"]), reverse=True),
        "long_candidates": [item["symbol"] for item in longs],
        "short_candidates": [item["symbol"] for item in shorts],
        "research_portfolio": {"weights": weights, "gross_exposure": round(gross, 8), "net_exposure": round(net, 8), "long_exposure": round(sum(value for value in weights.values() if value > 0), 8), "short_exposure": round(abs(sum(value for value in weights.values() if value < 0)), 8)},
        "execution_note": "Research portfolio without margin, securities lending, forced liquidation or other market rules; any short weight must pass execution risk controls again.",
        "research_only": True,
    }


def _allocate(candidates: list[dict[str, Any]], budget: float, cap: float, direction: str) -> dict[str, float]:
    if not candidates or budget <= 0:
        return {}
    per_name = min(cap, budget / len(candidates))
    signed = per_name if direction == "LONG" else -per_name
    return {item["symbol"]: round(signed, 8) for item in candidates}


def _universe_regime(signals: list[dict[str, Any]]) -> str:
    regimes = [item["market_regime"] for item in signals]
    if not regimes:
        return "NEUTRAL"
    bull = regimes.count("BULL")
    bear = regimes.count("BEAR")
    if bull > bear and bull >= max(1, len(regimes) / 2):
        return "BULL"
    if bear > bull and bear >= max(1, len(regimes) / 2):
        return "BEAR"
    return "NEUTRAL"


def _optional_float(value: object) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
