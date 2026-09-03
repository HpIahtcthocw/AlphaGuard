"""Simple baselines every strategy must beat honestly."""

from __future__ import annotations

import pandas as pd


def buy_and_hold_weights(prices: pd.DataFrame, max_weight: float = 1.0) -> pd.DataFrame:
    clean = _validate(prices)
    weights = pd.DataFrame(0.0, index=clean.index, columns=clean.columns)
    eligible = clean.iloc[0].dropna().index
    if len(eligible):
        weight = min(1.0 / len(eligible), max_weight)
        weights.loc[:, eligible] = weight
    return weights


def equal_weight_monthly(prices: pd.DataFrame, max_weight: float = 0.35) -> pd.DataFrame:
    clean = _validate(prices)
    weights = pd.DataFrame(0.0, index=clean.index, columns=clean.columns)
    periods = clean.index.to_period("M")
    rebalance = {clean.index[i] for i in range(len(clean)) if i == len(clean) - 1 or periods[i] != periods[i + 1]}
    current = pd.Series(0.0, index=clean.columns)
    for date in clean.index:
        if date in rebalance:
            eligible = clean.loc[date].dropna().index
            current[:] = 0.0
            if len(eligible):
                current.loc[eligible] = min(1.0 / len(eligible), max_weight)
        weights.loc[date] = current
    return weights


def trend_filter_equal_weight(prices: pd.DataFrame, trend_window: int = 200, max_weight: float = 0.35) -> pd.DataFrame:
    clean = _validate(prices)
    trend = clean > clean.rolling(trend_window, min_periods=trend_window).mean()
    counts = trend.sum(axis=1).astype(float)
    counts = counts.where(counts > 0)
    weights = trend.astype(float).div(counts, axis=0).fillna(0.0)
    return weights.clip(upper=max_weight)


def _validate(prices: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(prices.index, pd.DatetimeIndex) or prices.empty:
        raise ValueError("prices must be a non-empty DataFrame with a DatetimeIndex")
    return prices.astype(float).sort_index()
