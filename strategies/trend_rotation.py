"""A deliberately small, auditable ETF trend-rotation strategy.

Input format: a DataFrame with a DatetimeIndex and one column per instrument.
The output is a target-weight DataFrame. Signals are computed using data available
at the close and are intended to be executed on the next eligible session.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def generate_target_weights(
    prices: pd.DataFrame,
    lookback: int = 126,
    trend_window: int = 200,
    volatility_window: int = 20,
    max_positions: int = 2,
    max_weight: float = 0.35,
    target_volatility: float = 0.10,
    covariance_window: int = 60,
    rebalance_every: int | None = None,
) -> pd.DataFrame:
    """Return monthly target weights with cash represented by missing weight.

    The implementation intentionally uses only lagged information. A row at
    date *t* is a signal generated at the close of *t* and must be executed on
    the next trading day by the backtest engine.
    """
    _validate_inputs(prices, lookback, trend_window, volatility_window, max_positions, max_weight)
    clean = prices.astype(float).sort_index().replace([np.inf, -np.inf], np.nan)
    returns = clean.pct_change(fill_method=None)
    momentum = clean / clean.shift(lookback) - 1.0
    trend_ok = clean > clean.rolling(trend_window, min_periods=trend_window).mean()
    volatility = returns.rolling(volatility_window, min_periods=volatility_window).std() * np.sqrt(252)
    weights = pd.DataFrame(0.0, index=clean.index, columns=clean.columns)
    rebalance_dates = set(clean.index[::rebalance_every]) if rebalance_every else _month_end_sessions(clean.index)

    for date in clean.index:
        if date not in rebalance_dates:
            if weights.index.get_loc(date) > 0:
                weights.loc[date] = weights.iloc[weights.index.get_loc(date) - 1]
            continue
        eligible = momentum.loc[date].where(trend_ok.loc[date])
        eligible = eligible.dropna().sort_values(ascending=False).head(max_positions)
        if eligible.empty:
            continue
        inverse_vol = (1.0 / volatility.loc[date, eligible.index]).replace([np.inf, -np.inf], np.nan).dropna()
        if inverse_vol.empty:
            continue
        raw = inverse_vol / inverse_vol.sum()
        covariance = returns.loc[:date, raw.index].tail(covariance_window).cov() * 252
        portfolio_variance = float(raw.to_numpy() @ covariance.to_numpy() @ raw.to_numpy())
        portfolio_volatility = float(np.sqrt(max(portfolio_variance, 0.0)))
        scale = min(1.0, target_volatility / portfolio_volatility) if portfolio_volatility > 0 else 0.0
        candidate = (raw * scale).clip(upper=max_weight)
        if candidate.sum() > 1.0:
            candidate = candidate / candidate.sum()
        weights.loc[date, candidate.index] = candidate
    return weights


def _month_end_sessions(index: pd.DatetimeIndex) -> set[pd.Timestamp]:
    """Return the final available session in each calendar month."""
    periods = index.to_period("M")
    return {index[position] for position in range(len(index)) if position == len(index) - 1 or periods[position] != periods[position + 1]}


def _validate_inputs(
    prices: pd.DataFrame,
    lookback: int,
    trend_window: int,
    volatility_window: int,
    max_positions: int,
    max_weight: float,
) -> None:
    if not isinstance(prices.index, pd.DatetimeIndex):
        raise TypeError("prices must use a DatetimeIndex")
    if prices.empty or prices.columns.empty:
        raise ValueError("prices cannot be empty")
    if prices.isna().all().any():
        raise ValueError("prices contains an instrument with no observations")
    if min(lookback, trend_window, volatility_window) < 2:
        raise ValueError("windows must be >= 2")
    if max_positions < 1 or not 0 < max_weight <= 1:
        raise ValueError("invalid position constraints")
