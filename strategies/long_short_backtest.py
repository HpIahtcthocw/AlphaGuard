"""Conservative long/short research backtest with explicit financing risks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Mapping, Optional

import numpy as np
import pandas as pd

from .backtest import _metrics
from execution.market_rules import MarketRule, get_market_rules


@dataclass(frozen=True)
class LongShortBacktestConfig:
    initial_cash: float = 100_000.0
    commission_bps: float = 3.0
    slippage_bps: float = 5.0
    annual_borrow_bps: float = 300.0
    annual_margin_bps: float = 500.0
    maintenance_margin: float = 0.30
    max_gross_exposure: float = 1.50
    max_turnover: float = 1.00
    max_daily_loss: float = 0.10


@dataclass
class LongShortBacktestResult:
    equity: pd.Series
    positions: pd.DataFrame
    daily_returns: pd.Series
    metrics: Dict[str, float]
    warnings: list[str]
    turnover: pd.Series
    costs: pd.Series
    borrow_costs: pd.Series
    margin_costs: pd.Series
    forced_liquidations: pd.Series
    blocked_trade_days: pd.Series
    rule_warnings: list[str]


def run_long_short_backtest(
    prices: pd.DataFrame,
    target_weights: pd.DataFrame,
    config: Optional[LongShortBacktestConfig] = None,
    benchmark: Optional[pd.Series] = None,
    shortable: Optional[Mapping[str, bool]] = None,
    borrow_cost_bps: Optional[Mapping[str, float]] = None,
    market: Optional[str] = None,
    rules: Optional[MarketRule] = None,
) -> LongShortBacktestResult:
    config = config or LongShortBacktestConfig()
    prices, target_weights = _validate_and_align(prices, target_weights, config)
    shortable = shortable or {}
    borrow_cost_bps = borrow_cost_bps or {}
    rules = rules or (get_market_rules(market) if market else None)
    short_columns = [column for column in target_weights.columns if (target_weights[column] < 0).any()]
    if rules is not None and short_columns and not rules.supports_short:
        raise ValueError(f"{rules.market} market rules do not permit stock short selling")
    unavailable = [column for column in short_columns if not shortable.get(column, False)]
    if unavailable:
        raise ValueError(f"short positions require borrow availability: {', '.join(unavailable)}")

    returns = prices.pct_change(fill_method=None).fillna(0.0).to_numpy(dtype=float)
    execution = target_weights.shift(1).fillna(0.0).to_numpy(dtype=float)
    held_values = np.zeros_like(execution)
    equity_values = np.full(len(prices), config.initial_cash, dtype=float)
    daily_values = np.zeros(len(prices), dtype=float)
    turnover_values = np.zeros(len(prices), dtype=float)
    costs_values = np.zeros(len(prices), dtype=float)
    borrow_values = np.zeros(len(prices), dtype=float)
    margin_values = np.zeros(len(prices), dtype=float)
    forced_values = np.zeros(len(prices), dtype=bool)
    blocked_values = np.zeros(len(prices), dtype=bool)
    previous = np.zeros(len(prices.columns), dtype=float)
    warnings: list[str] = []
    rule_warnings: list[str] = []
    borrow_rates = np.array([float(borrow_cost_bps.get(column, config.annual_borrow_bps)) / 10_000 / 252 for column in prices.columns])
    margin_rate = config.annual_margin_bps / 10_000 / 252

    for index, date in enumerate(prices.index):
        desired = execution[index].copy()
        gross_exposure = float(np.abs(desired).sum())
        if gross_exposure > config.max_gross_exposure:
            desired *= config.max_gross_exposure / gross_exposure
            warnings.append(f"{date.date()}: gross exposure capped at {config.max_gross_exposure:.2f}x")
        turnover = float(np.abs(desired - previous).sum())
        if turnover > config.max_turnover:
            desired = previous + (desired - previous) * (config.max_turnover / turnover)
            turnover = config.max_turnover
            warnings.append(f"{date.date()}: turnover capped at {config.max_turnover:.2f}x")
        if rules is not None:
            desired, blocked = _apply_market_rules(desired, previous, prices.iloc[index], returns[index], equity_values[index - 1] if index else config.initial_cash, rules, date, rule_warnings)
            if blocked:
                blocked_values[index] = True
                turnover = float(np.abs(desired - previous).sum())
        turnover_values[index] = turnover
        trade_cost = turnover * (config.commission_bps + config.slippage_bps) / 10_000
        borrow_cost = float(np.abs(np.minimum(desired, 0.0)) @ borrow_rates)
        margin_notional = max(float(np.abs(desired).sum()) - 1.0, 0.0)
        margin_cost = margin_notional * margin_rate
        gross_return = float(desired @ returns[index])
        net_return = gross_return - trade_cost - borrow_cost - margin_cost
        if net_return < -config.max_daily_loss:
            warnings.append(f"{date.date()}: daily loss guard triggered at {net_return:.2%}")
            net_return = -config.max_daily_loss
        equity_values[index] = equity_values[index - 1] * (1 + net_return) if index else config.initial_cash
        maintenance_requirement = float(np.abs(np.minimum(desired, 0.0)).sum()) * config.maintenance_margin
        if maintenance_requirement > 0 and equity_values[index] / config.initial_cash < maintenance_requirement:
            forced_values[index] = True
            warnings.append(f"{date.date()}: maintenance margin breached; positions liquidated")
            desired = np.zeros_like(desired)
            previous = desired
        else:
            denominator = 1.0 + gross_return
            previous = desired * (1.0 + returns[index]) / denominator if denominator > 0 else desired
        held_values[index] = desired
        daily_values[index] = net_return
        costs_values[index] = trade_cost
        borrow_values[index] = borrow_cost
        margin_values[index] = margin_cost

    equity = pd.Series(equity_values, index=prices.index, dtype=float)
    daily_returns = pd.Series(daily_values, index=prices.index, dtype=float)
    turnover = pd.Series(turnover_values, index=prices.index, dtype=float)
    costs = pd.Series(costs_values, index=prices.index, dtype=float)
    borrow_costs = pd.Series(borrow_values, index=prices.index, dtype=float)
    margin_costs = pd.Series(margin_values, index=prices.index, dtype=float)
    forced_liquidations = pd.Series(forced_values, index=prices.index, dtype=bool)
    positions = pd.DataFrame(held_values, index=prices.index, columns=prices.columns)
    metrics = _metrics(equity, daily_returns, benchmark, turnover, costs + borrow_costs + margin_costs, 0.0)
    metrics.update({
        "borrow_cost_drag": float(borrow_costs.sum()),
        "margin_cost_drag": float(margin_costs.sum()),
        "forced_liquidation_count": float(forced_liquidations.sum()),
        "average_gross_exposure": float(np.abs(positions).sum(axis=1).mean()),
        "average_net_exposure": float(positions.sum(axis=1).mean()),
    })
    warnings.extend(rule_warnings)
    blocked_trade_days = pd.Series(blocked_values, index=prices.index, dtype=bool)
    return LongShortBacktestResult(
        equity, positions, daily_returns, metrics, sorted(set(warnings)), turnover,
        costs, borrow_costs, margin_costs, forced_liquidations, blocked_trade_days,
        sorted(set(rule_warnings)),
    )


def _apply_market_rules(
    desired: np.ndarray,
    previous: np.ndarray,
    prices: pd.Series,
    returns: np.ndarray,
    equity: float,
    rules: MarketRule,
    date: pd.Timestamp,
    warnings: list[str],
) -> tuple[np.ndarray, bool]:
    """Apply lot-size and price-limit approximations to target weights."""
    adjusted = desired.copy()
    blocked = False
    for idx, symbol in enumerate(prices.index):
        change = float(adjusted[idx] - previous[idx])
        if abs(change) > 1e-12:
            direction = "BUY" if change > 0 else "SELL"
            if adjusted[idx] < 0 and previous[idx] >= 0:
                direction = "SELL_SHORT"
            elif adjusted[idx] >= 0 and previous[idx] < 0:
                direction = "COVER"
            if rules.is_at_price_limit(float(returns[idx]), direction):
                adjusted[idx] = previous[idx]
                blocked = True
                warnings.append(f"{date.date()}: {symbol} {direction} blocked by {rules.market} daily price limit")
                continue
        # Weight-to-shares conversion is necessarily approximate because the
        # research engine has no broker cash ledger. Round down to a tradable
        # lot and preserve direction; this avoids inventing fractional CN lots.
        if abs(adjusted[idx]) > 1e-12 and prices.iloc[idx] > 0:
            shares = abs(float(equity) * float(adjusted[idx]) / float(prices.iloc[idx]))
            lots = int(shares // rules.lot_size)
            tradable_shares = lots * rules.lot_size
            if tradable_shares <= 0:
                adjusted[idx] = 0.0
                warnings.append(f"{date.date()}: {symbol} target below {rules.lot_size}-share lot; trade omitted")
            else:
                adjusted[idx] = np.sign(adjusted[idx]) * tradable_shares * float(prices.iloc[idx]) / max(float(equity), 1e-12)
    return adjusted, blocked


def _validate_and_align(prices: pd.DataFrame, weights: pd.DataFrame, config: LongShortBacktestConfig):
    if not isinstance(prices.index, pd.DatetimeIndex) or not isinstance(weights.index, pd.DatetimeIndex):
        raise TypeError("prices and target_weights must use DatetimeIndex")
    if prices.empty or not prices.index.is_monotonic_increasing:
        raise ValueError("prices must be non-empty and sorted")
    if (prices <= 0).any().any():
        raise ValueError("prices must be positive")
    weights = weights.reindex(index=prices.index, columns=prices.columns).fillna(0.0).astype(float)
    if config.initial_cash <= 0 or min(config.commission_bps, config.slippage_bps, config.annual_borrow_bps, config.annual_margin_bps, config.maintenance_margin, config.max_gross_exposure, config.max_turnover, config.max_daily_loss) < 0:
        raise ValueError("invalid long/short backtest configuration")
    if config.maintenance_margin > 1 or config.max_gross_exposure < 1:
        raise ValueError("maintenance_margin must be <= 1 and max_gross_exposure must be >= 1")
    return prices.astype(float), weights
