import numpy as np
import pandas as pd

from strategies.backtest import BacktestConfig, run_backtest
from strategies.trend_rotation import generate_target_weights
from research.validation import run_research_backtest


def sample_prices(days=520):
    dates = pd.date_range("2023-01-03", periods=days, freq="B")
    steps = np.linspace(0, 0.7, days)
    return pd.DataFrame(
        {
            "ETF_A": 100 * np.exp(steps),
            "ETF_B": 100 * np.exp(0.2 * steps),
            "ETF_C": 100 * np.exp(-0.05 * steps),
        },
        index=dates,
    )


def test_strategy_has_no_short_weights_and_respects_cap():
    prices = sample_prices()
    weights = generate_target_weights(prices, lookback=63, trend_window=100)
    assert (weights >= 0).all().all()
    assert (weights.sum(axis=1) <= 1.000001).all()
    assert (weights.max(axis=1) <= 0.350001).all()


def test_backtest_executes_on_next_session_and_reports_metrics():
    prices = sample_prices()
    weights = pd.DataFrame(0.0, index=prices.index, columns=prices.columns)
    weights.loc[prices.index[10], "ETF_A"] = 0.5
    result = run_backtest(prices, weights, BacktestConfig(commission_bps=0, slippage_bps=0))
    assert result.positions.loc[prices.index[10], "ETF_A"] == 0
    assert result.positions.loc[prices.index[11], "ETF_A"] == 0.5
    assert "max_drawdown" in result.metrics


def test_backtest_rejects_non_positive_prices():
    prices = sample_prices()
    prices.iloc[0, 0] = 0
    weights = pd.DataFrame(0.0, index=prices.index, columns=prices.columns)
    try:
        run_backtest(prices, weights)
    except ValueError as exc:
        assert "positive" in str(exc)
    else:
        raise AssertionError("expected invalid prices to be rejected")


def test_strategy_rebalances_on_last_available_session_of_month():
    prices = sample_prices(260)
    weights = generate_target_weights(prices, lookback=20, trend_window=40, volatility_window=10)
    changed = weights.diff().abs().sum(axis=1) > 1e-9
    changed_dates = weights.index[changed]
    assert len(changed_dates) > 0
    for date in changed_dates:
        month_sessions = weights.loc[str(date.to_period("M"))].index
        assert date == month_sessions[-1]


def test_research_report_contains_baselines_and_out_of_sample_metrics():
    report = run_research_backtest(sample_prices(), benchmark_symbol="ETF_A")
    assert set(report["baselines"]) == {"BASE-BUY-HOLD", "BASE-EQUAL", "BASE-TREND"}
    assert "max_drawdown" in report["out_of_sample_metrics"]
    assert len(report["walk_forward"]["folds"]) >= 1
    assert "annualized_return" in report["walk_forward"]["metrics"]
    assert report["data_fingerprint"]
    assert report["production_eligible"] is False
