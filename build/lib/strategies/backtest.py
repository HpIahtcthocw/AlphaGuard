"""A conservative daily backtest runner for target-weight strategies."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class BacktestConfig:
    initial_cash: float = 100_000.0
    commission_bps: float = 3.0
    slippage_bps: float = 5.0
    rebalance_threshold: float = 0.01
    max_turnover: float = 1.0
    annual_risk_free_rate: float = 0.0


@dataclass
class BacktestResult:
    equity: pd.Series
    positions: pd.DataFrame
    daily_returns: pd.Series
    metrics: Dict[str, float]
    warnings: list[str]
    turnover: pd.Series
    costs: pd.Series
    drawdown: pd.Series


def run_backtest(
    prices: pd.DataFrame,
    target_weights: pd.DataFrame,
    config: Optional[BacktestConfig] = None,
    benchmark: Optional[pd.Series] = None,
) -> BacktestResult:
    """Run target weights with next-day execution and explicit costs.

    Target weights are interpreted as end-of-day signals. The engine shifts
    them by one session before applying trades, preventing same-bar lookahead.
    """
    config = config or BacktestConfig()
    prices, target_weights = _validate_and_align(prices, target_weights, config)
    returns = prices.pct_change(fill_method=None).fillna(0.0)
    execution_weights = target_weights.shift(1).fillna(0.0)
    warnings: list[str] = []
    return_values = returns.to_numpy(dtype=float)
    execution_values = execution_weights.to_numpy(dtype=float)
    held_values = np.zeros_like(execution_values)
    equity_values = np.full(len(prices), config.initial_cash, dtype=float)
    daily_values = np.zeros(len(prices), dtype=float)
    turnover_values = np.zeros(len(prices), dtype=float)
    cost_values = np.zeros(len(prices), dtype=float)
    previous = np.zeros(len(prices.columns), dtype=float)

    for i, date in enumerate(prices.index):
        desired = np.clip(execution_values[i].copy(), 0.0, None)
        desired_sum = float(desired.sum())
        if desired_sum > 1.0:
            desired /= desired_sum
        turnover = float(np.abs(desired - previous).sum())
        if turnover < config.rebalance_threshold:
            desired = previous.copy()
            turnover = 0.0
        if turnover > config.max_turnover:
            warnings.append(f"{date.date()}: turnover {turnover:.2%} capped")
            desired = previous + (desired - previous) * (config.max_turnover / turnover)
            turnover = config.max_turnover
        turnover_values[i] = turnover
        trade_cost = turnover * (config.commission_bps + config.slippage_bps) / 10_000
        cost_values[i] = trade_cost
        held_values[i] = desired
        gross = float(np.dot(desired, return_values[i]))
        daily_values[i] = gross - trade_cost
        equity_values[i] = equity_values[i - 1] * (1 + daily_values[i]) if i else config.initial_cash
        denominator = 1.0 + gross
        previous = desired * (1.0 + return_values[i]) / denominator if denominator > 0 else desired

    held = pd.DataFrame(held_values, index=prices.index, columns=prices.columns)
    equity = pd.Series(equity_values, index=prices.index, dtype=float)
    daily_returns = pd.Series(daily_values, index=prices.index, dtype=float)
    turnover_series = pd.Series(turnover_values, index=prices.index, dtype=float)
    cost_series = pd.Series(cost_values, index=prices.index, dtype=float)

    drawdown = equity / equity.cummax() - 1
    metrics = _metrics(equity, daily_returns, benchmark, turnover_series, cost_series, config.annual_risk_free_rate)
    if (target_weights.sum(axis=1) > 1.000001).any():
        warnings.append("target weights exceeded 100%; rows were normalized")
    if len(prices) < 252:
        warnings.append("backtest contains less than one trading year")
    return BacktestResult(equity, held, daily_returns, metrics, sorted(set(warnings)), turnover_series, cost_series, drawdown)


def _validate_and_align(prices: pd.DataFrame, weights: pd.DataFrame, config: BacktestConfig):
    if not isinstance(prices.index, pd.DatetimeIndex) or not isinstance(weights.index, pd.DatetimeIndex):
        raise TypeError("prices and target_weights must use DatetimeIndex")
    if prices.empty or not prices.index.is_monotonic_increasing:
        raise ValueError("prices must be non-empty and sorted")
    if (prices <= 0).any().any():
        raise ValueError("prices must be positive")
    common = prices.index.intersection(weights.index)
    if len(common) < 2:
        raise ValueError("prices and target_weights need at least two common sessions")
    weights = weights.reindex(index=prices.index, columns=prices.columns).fillna(0.0)
    if (weights < 0).any().any():
        raise ValueError("short weights are not supported by this personal-investor baseline")
    if config.initial_cash <= 0 or min(config.commission_bps, config.slippage_bps, config.rebalance_threshold, config.max_turnover) < 0:
        raise ValueError("invalid backtest costs or cash")
    return prices.astype(float), weights.astype(float)


def _metrics(
    equity: pd.Series,
    daily_returns: pd.Series,
    benchmark: Optional[pd.Series],
    turnover: pd.Series,
    costs: pd.Series,
    annual_risk_free_rate: float,
) -> Dict[str, float]:
    years = max((len(equity) - 1) / 252, 1 / 252)
    total_return = float(equity.iloc[-1] / equity.iloc[0] - 1)
    annualized = float((1 + total_return) ** (1 / years) - 1) if total_return > -1 else -1.0
    volatility = float(daily_returns.std(ddof=0) * np.sqrt(252))
    daily_rf = (1 + annual_risk_free_rate) ** (1 / 252) - 1
    excess = daily_returns - daily_rf
    sharpe = float(excess.mean() / excess.std(ddof=0) * np.sqrt(252)) if excess.std(ddof=0) else 0.0
    downside = np.minimum(excess, 0.0)
    downside_volatility = float(np.sqrt(np.mean(np.square(downside))) * np.sqrt(252))
    sortino = float((annualized - annual_risk_free_rate) / downside_volatility) if downside_volatility else 0.0
    drawdown = equity / equity.cummax() - 1
    maximum_drawdown = float(drawdown.min())
    calmar = float(annualized / abs(maximum_drawdown)) if maximum_drawdown else 0.0
    losses = daily_returns[daily_returns < 0]
    var_95 = float(daily_returns.quantile(0.05))
    cvar_sample = daily_returns[daily_returns <= var_95]
    result = {
        "total_return": total_return,
        "annualized_return": annualized,
        "annualized_volatility": volatility,
        "max_drawdown": maximum_drawdown,
        "sharpe": sharpe,
        "sortino": sortino,
        "calmar": calmar,
        "downside_volatility": downside_volatility,
        "daily_var_95": var_95,
        "daily_cvar_95": float(cvar_sample.mean()) if len(cvar_sample) else var_95,
        "win_rate": float((daily_returns > 0).mean()),
        "loss_rate": float((daily_returns < 0).mean()),
        "annualized_turnover": float(turnover.sum() / years),
        "trade_days": float((turnover > 0).sum()),
        "cost_drag": float(costs.sum()),
        "final_equity": float(equity.iloc[-1]),
    }
    if benchmark is not None:
        aligned = benchmark.reindex(equity.index).dropna()
        if len(aligned) > 1:
            result["benchmark_return"] = float(aligned.iloc[-1] / aligned.iloc[0] - 1)
            result["excess_return"] = result["total_return"] - result["benchmark_return"]
            benchmark_returns = aligned.pct_change(fill_method=None).reindex(daily_returns.index).fillna(0.0)
            variance = float(benchmark_returns.var(ddof=0))
            beta = float(np.cov(daily_returns, benchmark_returns, ddof=0)[0, 1] / variance) if variance else 0.0
            result["beta"] = beta
            result["annualized_alpha"] = float((daily_returns.mean() - beta * benchmark_returns.mean()) * 252)
    return result
