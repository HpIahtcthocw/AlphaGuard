"""Deterministic strategy and backtest primitives for Personal Investment OS."""

from .backtest import BacktestConfig, BacktestResult, run_backtest
from .registry import STRATEGY_REGISTRY, get_strategy
from .trend_rotation import generate_target_weights

__all__ = [
    "BacktestConfig",
    "BacktestResult",
    "STRATEGY_REGISTRY",
    "generate_target_weights",
    "get_strategy",
    "run_backtest",
]
