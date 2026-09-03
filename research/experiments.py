"""Reproducible investment experiments owned by this project.

An experiment is a research protocol, not a performance promise. The default
experiment deliberately uses synthetic data so that it is deterministic and
safe to run in CI; the report therefore cannot become paper/live approval.
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from strategies.backtest import BacktestConfig, run_backtest
from .validation import run_research_backtest


EXPERIMENT_ID = "PIO-EXP-001"


def build_personal_experiment_prices(days: int = 1100, seed: int = 20260829) -> pd.DataFrame:
    """Create a deterministic multi-market stress path for the first experiment."""
    if days < 400:
        raise ValueError("personal experiment requires at least 400 sessions")
    dates = pd.bdate_range("2021-01-04", periods=days)
    rng = np.random.default_rng(seed)
    regime = np.zeros(days)
    regime[: days // 4] = 0.00035
    regime[days // 4 : days // 4 + days // 8] = -0.00065
    regime[days // 4 + days // 8 : days // 2] = 0.00015
    regime[days // 2 : 3 * days // 4] = 0.00045
    regime[3 * days // 4 :] = -0.00020
    common = regime + rng.normal(0.0, 0.009, days)
    defensive = 0.00012 + 0.35 * regime + rng.normal(0.0, 0.0035, days)
    bonds = 0.00010 - 0.05 * regime + rng.normal(0.0, 0.0022, days)
    cn = 0.00002 + 0.85 * common + rng.normal(0.0, 0.005, days)
    us = 0.00004 + 0.95 * common + rng.normal(0.0, 0.004, days)
    return pd.DataFrame(
        {
            "US_EQ": 100 * np.exp(np.cumsum(us)),
            "CN_EQ": 100 * np.exp(np.cumsum(cn)),
            "DEFENSIVE": 100 * np.exp(np.cumsum(defensive)),
            "BONDS": 100 * np.exp(np.cumsum(bonds)),
        },
        index=dates,
    )


def run_personal_investment_experiment(
    prices: Optional[pd.DataFrame] = None,
    dataset_kind: str = "SYNTHETIC",
    benchmark_symbol: str = "US_EQ",
    source_note: Optional[str] = None,
) -> dict[str, object]:
    """Run PIO-EXP-001 and return evidence, gates and a non-promotional verdict."""
    clean = prices.astype(float).sort_index() if prices is not None else build_personal_experiment_prices()
    if benchmark_symbol not in clean.columns:
        benchmark_symbol = str(clean.columns[0])
        source_note = (source_note + "; " if source_note else "") + "benchmark_symbol absent; first available symbol selected"
    report = run_research_backtest(
        clean,
        strategy_id="S-001",
        parameters={
            "lookback": 126,
            "trend_window": 200,
            "volatility_window": 20,
            "max_positions": 2,
            "max_weight": 0.35,
            "target_volatility": 0.10,
            "covariance_window": 60,
        },
        config=BacktestConfig(initial_cash=100_000, commission_bps=3, slippage_bps=5),
        benchmark_symbol=benchmark_symbol,
        split_ratio=0.70,
        dataset_kind=dataset_kind,
        walk_forward_train_window=504,
        walk_forward_test_window=126,
    )
    out = report["out_of_sample_metrics"]
    baseline = report["baselines"]["BASE-BUY-HOLD"]["metrics"]
    gates = [
        {"code": "DATA_PROVENANCE", "status": "PASS" if dataset_kind.upper() == "REAL_MARKET_DATA" else "BLOCKED", "message": "Authorized real historical market data" if dataset_kind.upper() == "REAL_MARKET_DATA" else "Current experiment data is not authorized real market data"},
        {"code": "OOS_DRAWDOWN", "status": "PASS" if out["max_drawdown"] >= baseline["max_drawdown"] else "WARN", "message": f"Out-of-sample max drawdown {out['max_drawdown']:.2%}; buy-and-hold baseline {baseline['max_drawdown']:.2%}"},
        {"code": "WALK_FORWARD", "status": "PASS" if len(report["walk_forward"]["folds"]) >= 3 else "BLOCKED", "message": f"walk-forward folds={len(report['walk_forward']['folds'])}"},
        {"code": "PAPER_RECONCILIATION", "status": "BLOCKED", "message": "Four consecutive weeks of paper-trading and brokerage return reconciliation not yet completed"},
    ]
    return {
        "experiment_id": EXPERIMENT_ID,
        "title": "Personal Investment OS: multi-market defensive trend rotation experiment v1",
        "hypothesis": "In a mixed environment of A-share/US equity proxy assets with trend regime switches, trend filtering, inverse-volatility weighting and portfolio volatility targeting have the opportunity to reduce out-of-sample drawdown; no improvement in returns is promised.",
        "protocol": {
            "strategy_id": "S-001",
            "rebalance": "calendar-month-end; next-session execution",
            "cost_model": {"commission_bps": 3, "slippage_bps": 5},
            "benchmark": f"{benchmark_symbol} buy-and-hold",
            "dataset_kind": dataset_kind.upper(),
            "source_note": source_note,
            "execution_mode": "research-only; no order intent created",
        },
        "evidence": report,
        # Top-level aliases keep the report consumable by the existing
        # backtest UI while preserving the explicit experiment envelope.
        "dataset_kind": report["dataset_kind"],
        "strategy": report["strategy"],
        "period": report["period"],
        "split": report["split"],
        "metrics": report["metrics"],
        "baselines": report["baselines"],
        "equity": report["equity"],
        "data_quality": report["data_quality"],
        "warnings": report["warnings"],
        "production_eligible": False,
        "gates": gates,
        "verdict": "RESEARCH_ONLY" if dataset_kind.upper() != "REAL_MARKET_DATA" else "NOT_READY",
        "next_action": "Replace with real, adjusted, point-in-time data, re-run the same protocol, then enter paper trading; do not place orders based on synthetic experiment results.",
    }


def ohlcv_to_close_prices(frame: pd.DataFrame) -> tuple[pd.DataFrame, str]:
    """Pivot validated long OHLCV rows into the close matrix used by S-001.

    Adjusted close is preferred only when it is complete for every symbol;
    otherwise the raw close is used and the caller receives an explicit note.
    """
    required = {"date", "symbol", "close"}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"OHLCV frame missing columns: {', '.join(missing)}")
    value_column = "close"
    note = "using raw close"
    if "adjusted_close" in frame.columns:
        adjusted = pd.to_numeric(frame["adjusted_close"], errors="coerce")
        if adjusted.notna().all():
            value_column = "adjusted_close"
            note = "using complete adjusted_close"
        else:
            note = "adjusted_close incomplete; using raw close"
    data = frame.copy()
    data["date"] = pd.to_datetime(data["date"])
    data["symbol"] = data["symbol"].astype(str).str.strip().str.upper()
    data[value_column] = pd.to_numeric(data[value_column], errors="coerce")
    matrix = data.pivot(index="date", columns="symbol", values=value_column).sort_index()
    if matrix.shape[1] < 2:
        raise ValueError("personal experiment requires at least two symbols")
    if matrix.isna().any().any():
        raise ValueError("OHLCV close matrix contains missing symbol/date observations")
    return matrix.astype(float), note
