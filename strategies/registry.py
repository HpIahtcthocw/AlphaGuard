"""Strategy provenance, licensing posture, and production eligibility."""

from dataclasses import dataclass
from typing import Callable, Dict, Optional

import pandas as pd

from .baselines import buy_and_hold_weights, equal_weight_monthly, trend_filter_equal_weight
from .trend_rotation import generate_target_weights


@dataclass(frozen=True)
class StrategySpec:
    strategy_id: str
    name: str
    version: str
    provenance: str
    license_note: str
    risk_level: str
    rebalance_frequency: str
    supports_paper: bool
    production_eligible: bool
    generator: Optional[Callable[..., object]]
    mode: str = "portfolio"


def _load_regime_breakout():
    from .regime_breakout import evaluate_breakout_signal

    return evaluate_breakout_signal


STRATEGY_REGISTRY: Dict[str, StrategySpec] = {
    "S-001": StrategySpec(
        strategy_id="S-001",
        name="Defensive ETF Trend Rotation",
        version="0.2.0",
        provenance="In-house implementation; methodology draws on time-series momentum, trend filtering, inverse-volatility weighting and portfolio volatility targeting",
        license_note="Project-owned implementation; does not copy third-party source code",
        risk_level="medium",
        rebalance_frequency="calendar-month-end",
        supports_paper=True,
        production_eligible=False,
        generator=generate_target_weights,
    ),
    "S-003": StrategySpec(
        strategy_id="S-003",
        name="Regime-driven long/short breakout",
        version="0.1.0",
        provenance="In-house implementation; draws on trend following, Donchian breakout, volume-price confirmation and regime filtering",
        license_note="Project-owned implementation; does not copy third-party source code",
        risk_level="high",
        rebalance_frequency="event-driven",
        supports_paper=False,
        production_eligible=False,
        generator=_load_regime_breakout,
        mode="signal-only",
    ),
    "BASE-BUY-HOLD": StrategySpec(
        "BASE-BUY-HOLD", "Buy-and-Hold Baseline", "1.0.0", "Standard research baseline", "Project-owned implementation", "market", "once", False, False, buy_and_hold_weights
    ),
    "BASE-EQUAL": StrategySpec(
        "BASE-EQUAL", "Monthly Equal-Weight Baseline", "1.0.0", "Standard research baseline", "Project-owned implementation", "market", "calendar-month-end", False, False, equal_weight_monthly
    ),
    "BASE-TREND": StrategySpec(
        "BASE-TREND", "Trend-Filtered Baseline", "1.0.0", "Standard research baseline", "Project-owned implementation", "medium", "daily", False, False, trend_filter_equal_weight
    ),
}


def get_strategy(strategy_id: str) -> StrategySpec:
    try:
        return STRATEGY_REGISTRY[strategy_id]
    except KeyError as exc:
        raise ValueError(f"Unknown strategy: {strategy_id}") from exc
