"""Market-regime-aware long/short breakout research strategy."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping, Optional

import pandas as pd

from research.factors import compute_factors


@dataclass(frozen=True)
class BreakoutConfig:
    long_daily_return: float = 0.10
    long_volume_ratio: float = 4.0
    long_breakout_count: float = 3.0
    long_surge_count: float = 2.0
    long_drawdown_20d: float = -0.02
    long_drawdown_120d: float = -0.05
    short_return_20d: float = -0.05
    short_support_break_count: float = 2.0
    short_crash_count: float = 2.0
    short_drawdown_20d: float = -0.03
    regime_confirmation_days: int = 3
    require_hard_core: int = 3


def evaluate_breakout_signal(
    bars: pd.DataFrame,
    benchmark_close: Optional[pd.Series],
    market: str,
    symbol: str,
    shortable: bool = False,
    borrow_cost_bps: Optional[float] = None,
    config: Optional[BreakoutConfig] = None,
) -> dict[str, Any]:
    config = config or BreakoutConfig()
    features = compute_factors(bars, benchmark_close)
    latest = features.iloc[-1]
    regime = _confirmed_regime(features["market_trend"], config.regime_confirmation_days)
    long_conditions = {
        "bull_regime": regime == "BULL",
        "daily_surge": _safe(latest["ret_1d"]) >= config.long_daily_return,
        "volume_confirmation": _safe(latest["volume_ratio_5d"]) >= config.long_volume_ratio,
        "repeated_year_high_breakouts": _safe(latest["breakout_count_20d"]) >= config.long_breakout_count,
        "repeated_large_up_days": _safe(latest["surge_count_20d"]) >= config.long_surge_count,
        "shallow_month_drawdown": _safe(latest["drawdown_20d"]) >= config.long_drawdown_20d,
        "shallow_half_year_drawdown": _safe(latest["drawdown_120d"]) >= config.long_drawdown_120d,
        "above_short_medium_ma": _safe(latest["ma_dist_7d"]) > 0 and _safe(latest["ma_dist_30d"]) > 0,
        "up_volume_dominates": _safe(latest["up_down_volume_ratio_20d"]) > 1.0,
    }
    short_conditions = {
        "bear_regime": regime == "BEAR",
        "twenty_day_selloff": _safe(latest["ret_20d"]) <= config.short_return_20d,
        "repeated_support_breaks": _safe(latest["support_break_count_20d"]) >= config.short_support_break_count,
        "repeated_large_down_days": _safe(latest["crash_count_20d"]) >= config.short_crash_count,
        "below_short_medium_ma": _safe(latest["ma_dist_7d"]) < 0 and _safe(latest["ma_dist_30d"]) < 0,
        "drawdown_not_exhausted": _safe(latest["drawdown_20d"]) <= config.short_drawdown_20d,
        "down_volume_dominates": _safe(latest["up_down_volume_ratio_20d"]) < 1.0,
    }
    long_score = sum(long_conditions.values()) / len(long_conditions)
    short_score = sum(short_conditions.values()) / len(short_conditions)
    long_hard = sum(long_conditions[key] for key in ("bull_regime", "daily_surge", "volume_confirmation", "repeated_year_high_breakouts"))
    short_hard = sum(short_conditions[key] for key in ("bear_regime", "twenty_day_selloff", "repeated_support_breaks"))
    if long_hard >= config.require_hard_core and long_score > short_score:
        direction = "LONG"
    elif short_hard >= config.require_hard_core and short_score > long_score:
        direction = "SHORT"
    else:
        direction = "FLAT"
    short_reason = "可借券条件未验证"
    if direction == "SHORT" and shortable:
        short_reason = "可借券字段已提供，仍需实时券源和保证金检查"
    elif direction == "SHORT":
        short_reason = "信号成立但不可执行：缺少可借券确认"
    return {
        "symbol": symbol.upper(), "market": market.upper(), "as_of": bars.index[-1].isoformat(),
        "strategy_id": "S-003", "strategy_version": "0.1.0", "direction": direction,
        "market_regime": regime, "long_score": round(float(long_score), 6), "short_score": round(float(short_score), 6),
        "long_conditions": long_conditions, "short_conditions": short_conditions,
        "factors": {key: _json_number(value) for key, value in latest.to_dict().items()},
        "short_executable": bool(direction == "SHORT" and shortable), "shortability_note": short_reason,
        "borrow_cost_bps": borrow_cost_bps, "data_quality": {"bars": int(len(bars)), "has_252_sessions": bool(len(bars) >= 252), "missing_factor_count": int(latest.isna().sum())},
        "research_only": True, "reasons": _reasons(direction, long_conditions, short_conditions, short_reason), "config": asdict(config),
    }


def _confirmed_regime(series: pd.Series, days: int) -> str:
    tail = series.fillna(0.0).iloc[-max(days, 1):]
    if len(tail) < max(days, 1):
        return "NEUTRAL"
    if (tail > 0).all():
        return "BULL"
    if (tail < 0).all():
        return "BEAR"
    return "NEUTRAL"


def _safe(value: object) -> float:
    try:
        return float(value) if pd.notna(value) else float("nan")
    except (TypeError, ValueError):
        return float("nan")


def _json_number(value: object) -> Optional[float]:
    number = _safe(value)
    return None if pd.isna(number) else round(number, 8)


def _reasons(direction: str, long_conditions: Mapping[str, bool], short_conditions: Mapping[str, bool], short_reason: str) -> list[str]:
    if direction == "LONG":
        return [key for key, passed in long_conditions.items() if passed]
    if direction == "SHORT":
        return [key for key, passed in short_conditions.items() if passed] + [short_reason]
    return ["核心条件不足，保持观察"]
