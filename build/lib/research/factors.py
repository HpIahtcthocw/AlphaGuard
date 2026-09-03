"""Versioned, explainable OHLCV factors used by research strategies."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Dict, Iterable, Optional

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class FactorSpec:
    factor_id: str
    name: str
    definition: str
    inputs: tuple[str, ...]
    horizon: str
    direction: str
    markets: tuple[str, ...]
    version: str = "1.0.0"
    lookahead_safe: bool = True
    known_risks: str = ""


FACTOR_REGISTRY: Dict[str, FactorSpec] = {
    "RET-1D": FactorSpec("RET-1D", "单日收益", "close / close[-1] - 1", ("close",), "1d", "higher-is-stronger", ("CN", "US", "HK")),
    "RET-20D": FactorSpec("RET-20D", "20日收益", "close / close[-20] - 1", ("close",), "20d", "higher-is-stronger", ("CN", "US", "HK")),
    "MOM-126D": FactorSpec("MOM-126D", "126日动量", "close / close[-126] - 1", ("close",), "126d", "higher-is-stronger", ("CN", "US", "HK")),
    "VOL-RATIO-5D": FactorSpec("VOL-RATIO-5D", "5日量比", "volume / mean(volume[-5:-1])", ("volume",), "5d", "higher-is-stronger", ("CN", "US", "HK")),
    "BREAKOUT-252D": FactorSpec("BREAKOUT-252D", "252日新高突破", "close > max(close[-252:-1])", ("close",), "252d", "higher-is-stronger", ("CN", "US", "HK"), known_risks="需要复权价格和足够历史长度"),
    "BREAKOUT-COUNT-20D": FactorSpec("BREAKOUT-COUNT-20D", "20日有效年高突破次数", "rolling sum of first-breakout events", ("close",), "20d", "higher-is-stronger", ("CN", "US", "HK"), known_risks="连续站在高位不重复计数"),
    "SURGE-COUNT-20D": FactorSpec("SURGE-COUNT-20D", "20日大涨事件次数", "count(return >= 10%)", ("close",), "20d", "higher-is-stronger", ("CN", "US", "HK"), known_risks="不是跨市场统一涨停规则"),
    "CRASH-COUNT-20D": FactorSpec("CRASH-COUNT-20D", "20日大跌事件次数", "count(return <= -10%)", ("close",), "20d", "higher-is-stronger", ("CN", "US", "HK"), known_risks="不是跨市场统一跌停规则"),
    "DRAWDOWN-20D": FactorSpec("DRAWDOWN-20D", "20日回撤", "close / rolling_max(close,20) - 1", ("close",), "20d", "lower-is-better", ("CN", "US", "HK")),
    "DRAWDOWN-120D": FactorSpec("DRAWDOWN-120D", "120日回撤", "close / rolling_max(close,120) - 1", ("close",), "120d", "lower-is-better", ("CN", "US", "HK")),
    "UP-DOWN-VOLUME-20D": FactorSpec("UP-DOWN-VOLUME-20D", "上涨/下跌成交量比", "sum(volume on up days) / sum(volume on down days)", ("close", "volume"), "20d", "higher-is-stronger", ("CN", "US", "HK")),
    "MA-DIST-7D": FactorSpec("MA-DIST-7D", "相对MA7距离", "close / MA7 - 1", ("close",), "7d", "higher-is-stronger", ("CN", "US", "HK")),
    "MA-DIST-30D": FactorSpec("MA-DIST-30D", "相对MA30距离", "close / MA30 - 1", ("close",), "30d", "higher-is-stronger", ("CN", "US", "HK")),
    "MA-DIST-60D": FactorSpec("MA-DIST-60D", "相对MA60距离", "close / MA60 - 1", ("close",), "60d", "higher-is-stronger", ("CN", "US", "HK")),
    "SUPPORT-BREAK-20D": FactorSpec("SUPPORT-BREAK-20D", "20日支撑跌破次数", "count(close < prior rolling low)", ("close",), "20d", "lower-is-better", ("CN", "US", "HK")),
    "MARKET-RET-20D": FactorSpec("MARKET-RET-20D", "市场20日收益", "benchmark close / close[-20] - 1", ("benchmark_close",), "20d", "regime", ("CN", "US", "HK")),
    "MARKET-TREND": FactorSpec("MARKET-TREND", "市场趋势状态", "benchmark close above/below MA60 and MA120", ("benchmark_close",), "60/120d", "regime", ("CN", "US", "HK")),
}


def list_factors(market: Optional[str] = None) -> list[dict[str, object]]:
    market = market.upper() if market else None
    return [asdict(spec) for spec in FACTOR_REGISTRY.values() if not market or market in spec.markets]


def compute_factors(bars: pd.DataFrame, benchmark_close: Optional[pd.Series] = None) -> pd.DataFrame:
    required = {"close", "volume"}
    missing = required - set(bars.columns)
    if missing:
        raise ValueError(f"bars missing columns: {', '.join(sorted(missing))}")
    if not isinstance(bars.index, pd.DatetimeIndex):
        raise TypeError("bars must use a DatetimeIndex")
    if bars.empty or not bars.index.is_monotonic_increasing:
        raise ValueError("bars must be non-empty and sorted")
    if (bars["close"] <= 0).any() or (bars["volume"] < 0).any():
        raise ValueError("close must be positive and volume cannot be negative")
    close = bars["close"].astype(float)
    volume = bars["volume"].astype(float)
    returns = close.pct_change(fill_method=None)
    features = pd.DataFrame(index=bars.index)
    features["ret_1d"] = returns
    features["ret_20d"] = close / close.shift(20) - 1
    features["mom_126d"] = close / close.shift(126) - 1
    prior_volume = volume.shift(1).rolling(5, min_periods=5).mean()
    features["volume_ratio_5d"] = volume / prior_volume.replace(0, np.nan)
    prior_high = close.shift(1).rolling(252, min_periods=252).max()
    previous_prior_high = close.shift(2).rolling(252, min_periods=252).max()
    first_breakout = (close > prior_high) & ~(close.shift(1) > previous_prior_high)
    features["breakout_252d"] = (close > prior_high).astype(float)
    features["breakout_count_20d"] = first_breakout.astype(float).rolling(20, min_periods=1).sum()
    features["surge_count_20d"] = (returns >= 0.10).astype(float).rolling(20, min_periods=1).sum()
    features["crash_count_20d"] = (returns <= -0.10).astype(float).rolling(20, min_periods=1).sum()
    features["drawdown_20d"] = close / close.rolling(20, min_periods=1).max() - 1
    features["drawdown_120d"] = close / close.rolling(120, min_periods=1).max() - 1
    up_volume = volume.where(returns > 0, 0.0).rolling(20, min_periods=5).sum()
    down_volume = volume.where(returns < 0, 0.0).rolling(20, min_periods=5).sum()
    features["up_down_volume_ratio_20d"] = up_volume / down_volume.replace(0, np.nan)
    for window in (7, 30, 60):
        features[f"ma_dist_{window}d"] = close / close.rolling(window, min_periods=window).mean() - 1
    prior_low = close.shift(1).rolling(20, min_periods=20).min()
    previous_prior_low = close.shift(2).rolling(20, min_periods=20).min()
    support_break = (close < prior_low) & ~(close.shift(1) < previous_prior_low)
    features["support_break_count_20d"] = support_break.astype(float).rolling(20, min_periods=1).sum()
    if benchmark_close is not None:
        benchmark = benchmark_close.reindex(bars.index).astype(float)
        features["market_ret_20d"] = benchmark / benchmark.shift(20) - 1
        ma60 = benchmark.rolling(60, min_periods=60).mean()
        ma120 = benchmark.rolling(120, min_periods=120).mean()
        features["market_trend"] = np.select([(benchmark > ma60) & (benchmark > ma120), (benchmark < ma60) & (benchmark < ma120)], [1.0, -1.0], default=0.0)
    else:
        features["market_ret_20d"] = np.nan
        features["market_trend"] = 0.0
    return features.replace([np.inf, -np.inf], np.nan)
