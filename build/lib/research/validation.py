"""Audited strategy comparison with explicit in/out-of-sample reporting."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from typing import Mapping, Optional

import numpy as np
import pandas as pd

from strategies.backtest import BacktestConfig, _metrics, run_backtest
from strategies.registry import STRATEGY_REGISTRY, get_strategy


BASELINES = ("BASE-BUY-HOLD", "BASE-EQUAL", "BASE-TREND")


def run_research_backtest(
    prices: pd.DataFrame,
    strategy_id: str = "S-001",
    parameters: Optional[Mapping[str, object]] = None,
    config: Optional[BacktestConfig] = None,
    benchmark_symbol: Optional[str] = None,
    split_ratio: float = 0.70,
    dataset_kind: str = "USER_PROVIDED",
    walk_forward_train_window: int = 252,
    walk_forward_test_window: int = 63,
) -> dict[str, object]:
    quality = audit_prices(prices)
    if quality["errors"]:
        raise ValueError("; ".join(quality["errors"]))
    clean = prices.astype(float).sort_index()
    strategy = get_strategy(strategy_id)
    if strategy.mode != "portfolio" or strategy.generator is None:
        raise ValueError(f"strategy {strategy_id} is signal-only and cannot be used by the portfolio backtest endpoint")
    weights = strategy.generator(clean, **dict(parameters or {}))
    benchmark = clean[benchmark_symbol] if benchmark_symbol else None
    result = run_backtest(clean, weights, config, benchmark)
    split = max(2, min(len(clean) - 2, int(len(clean) * split_ratio)))
    train = _segment(clean.iloc[: split + 1], weights.iloc[: split + 1], config, benchmark)
    test_start = max(split - 1, 0)
    test = _segment(clean.iloc[test_start:], weights.iloc[test_start:], config, benchmark)
    walk_forward = run_walk_forward(clean, strategy_id, parameters, config, benchmark, walk_forward_train_window, walk_forward_test_window)
    baselines: dict[str, object] = {}
    for baseline_id in BASELINES:
        baseline = STRATEGY_REGISTRY[baseline_id]
        baseline_weights = baseline.generator(clean)
        baseline_result = run_backtest(clean, baseline_weights, config, benchmark)
        baseline_payload: dict[str, object] = {"name": baseline.name, "metrics": baseline_result.metrics}
        if baseline_id == "BASE-BUY-HOLD":
            baseline_payload["equity"] = [{"date": index.date().isoformat(), "value": round(float(value), 4)} for index, value in baseline_result.equity.items()]
        baselines[baseline_id] = baseline_payload
    equity_points = [{"date": index.date().isoformat(), "value": round(float(value), 4)} for index, value in result.equity.items()]
    return {
        "strategy": _strategy_dict(strategy),
        "dataset_kind": dataset_kind,
        "data_fingerprint": fingerprint_prices(clean),
        "data_quality": quality,
        "period": {"start": clean.index[0].date().isoformat(), "end": clean.index[-1].date().isoformat(), "sessions": len(clean)},
        "split": {"train_end": clean.index[split].date().isoformat(), "test_start": clean.index[split + 1].date().isoformat()},
        "metrics": result.metrics,
        "train_metrics": train,
        "out_of_sample_metrics": test,
        "walk_forward": walk_forward,
        "baselines": baselines,
        "warnings": result.warnings,
        "equity": equity_points,
        "production_eligible": False,
        "eligibility_reasons": [
            "requires independent data-vendor reconciliation",
            "requires walk-forward parameter stability and stress scenarios",
            "requires at least four weeks of paper-trading reconciliation",
        ],
    }


def audit_prices(prices: pd.DataFrame) -> dict[str, object]:
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(prices.index, pd.DatetimeIndex):
        errors.append("prices must use a DatetimeIndex")
        return {"errors": errors, "warnings": warnings}
    if prices.empty or prices.columns.empty:
        errors.append("prices cannot be empty")
        return {"errors": errors, "warnings": warnings}
    if prices.index.has_duplicates:
        errors.append("duplicate sessions detected")
    if not prices.index.is_monotonic_increasing:
        errors.append("sessions are not sorted")
    if (prices <= 0).any().any():
        errors.append("non-positive prices detected")
    missing = int(prices.isna().sum().sum())
    missing_ratio = float(missing / prices.size)
    if missing_ratio > 0:
        warnings.append(f"missing price ratio: {missing_ratio:.2%}")
    if len(prices) < 252:
        warnings.append("less than one trading year of observations")
    returns = prices.pct_change(fill_method=None)
    extreme = int((returns.abs() > 0.30).sum().sum())
    if extreme:
        warnings.append(f"{extreme} daily moves exceed 30%; corporate actions or bad ticks must be reviewed")
    return {
        "errors": errors,
        "warnings": warnings,
        "missing_values": missing,
        "missing_ratio": missing_ratio,
        "extreme_move_count": extreme,
        "instruments": list(prices.columns),
    }


def fingerprint_prices(prices: pd.DataFrame) -> str:
    payload = {"index": [str(item) for item in prices.index], "columns": list(prices.columns), "values": prices.where(pd.notna(prices), None).values.tolist()}
    return hashlib.sha256(json.dumps(payload, separators=(",", ":"), default=str).encode()).hexdigest()


def run_walk_forward(
    prices: pd.DataFrame,
    strategy_id: str,
    parameters: Optional[Mapping[str, object]],
    config: Optional[BacktestConfig],
    benchmark: Optional[pd.Series],
    train_window: int = 252,
    test_window: int = 63,
) -> dict[str, object]:
    """Re-fit the rule on expanding information sets and score unseen blocks."""
    if len(prices) < train_window + 2:
        return {"folds": [], "metrics": {}, "warning": "insufficient sessions for walk-forward validation"}
    strategy = get_strategy(strategy_id)
    config = config or BacktestConfig()
    returns: list[pd.Series] = []
    turnovers: list[pd.Series] = []
    costs: list[pd.Series] = []
    folds: list[dict[str, object]] = []
    train_end = train_window
    while train_end < len(prices):
        test_end = min(train_end + test_window, len(prices))
        information_set = prices.iloc[:test_end]
        generated = strategy.generator(information_set, **dict(parameters or {}))
        start = max(train_end - 1, 0)
        segment_prices = prices.iloc[start:test_end]
        segment_weights = generated.iloc[start:test_end]
        segment_benchmark = benchmark.iloc[start:test_end] if benchmark is not None else None
        result = run_backtest(segment_prices, segment_weights, config, segment_benchmark)
        test_returns = result.daily_returns.iloc[1:]
        returns.append(test_returns)
        turnovers.append(result.turnover.iloc[1:])
        costs.append(result.costs.iloc[1:])
        folds.append(
            {
                "train_start": prices.index[0].date().isoformat(),
                "train_end": prices.index[train_end - 1].date().isoformat(),
                "test_start": prices.index[train_end].date().isoformat(),
                "test_end": prices.index[test_end - 1].date().isoformat(),
                "metrics": _metrics(result.equity.iloc[1:], test_returns, segment_benchmark.iloc[1:] if segment_benchmark is not None else None, result.turnover.iloc[1:], result.costs.iloc[1:], config.annual_risk_free_rate),
            }
        )
        train_end = test_end
    if not returns:
        return {"folds": [], "metrics": {}, "warning": "no walk-forward test blocks"}
    combined_returns = pd.concat(returns)
    combined_turnover = pd.concat(turnovers)
    combined_costs = pd.concat(costs)
    combined_equity = pd.Series(config.initial_cash * (1 + combined_returns).cumprod(), index=combined_returns.index)
    combined_benchmark = None
    if benchmark is not None:
        combined_benchmark = benchmark.reindex(combined_returns.index)
    metrics = _metrics(combined_equity, combined_returns, combined_benchmark, combined_turnover, combined_costs, config.annual_risk_free_rate)
    return {"folds": folds, "metrics": metrics, "train_window": train_window, "test_window": test_window}


def _segment(prices: pd.DataFrame, weights: pd.DataFrame, config: Optional[BacktestConfig], benchmark: Optional[pd.Series]) -> dict[str, float]:
    segment_benchmark = benchmark.reindex(prices.index) if benchmark is not None else None
    return run_backtest(prices, weights, config, segment_benchmark).metrics


def _strategy_dict(strategy) -> dict[str, object]:
    data = asdict(strategy)
    data.pop("generator", None)
    return data
