"""Strategy provenance, licensing posture, and production eligibility."""

from dataclasses import dataclass
from typing import Callable, Dict

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
    generator: Callable[..., pd.DataFrame]


STRATEGY_REGISTRY: Dict[str, StrategySpec] = {
    "S-001": StrategySpec(
        strategy_id="S-001",
        name="防御型 ETF 趋势轮动",
        version="0.2.0",
        provenance="自研实现；方法借鉴时间序列动量、趋势过滤、逆波动率与组合波动率目标",
        license_note="项目自有实现，不复制第三方源代码",
        risk_level="medium",
        rebalance_frequency="calendar-month-end",
        supports_paper=True,
        production_eligible=False,
        generator=generate_target_weights,
    ),
    "BASE-BUY-HOLD": StrategySpec(
        "BASE-BUY-HOLD", "买入持有基线", "1.0.0", "标准研究基线", "项目自有实现", "market", "once", False, False, buy_and_hold_weights
    ),
    "BASE-EQUAL": StrategySpec(
        "BASE-EQUAL", "月度等权基线", "1.0.0", "标准研究基线", "项目自有实现", "market", "calendar-month-end", False, False, equal_weight_monthly
    ),
    "BASE-TREND": StrategySpec(
        "BASE-TREND", "趋势过滤基线", "1.0.0", "标准研究基线", "项目自有实现", "medium", "daily", False, False, trend_filter_equal_weight
    ),
}


def get_strategy(strategy_id: str) -> StrategySpec:
    try:
        return STRATEGY_REGISTRY[strategy_id]
    except KeyError as exc:
        raise ValueError(f"Unknown strategy: {strategy_id}") from exc
