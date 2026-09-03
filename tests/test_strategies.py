import numpy as np
import pandas as pd

from strategies.backtest import BacktestConfig, run_backtest
from strategies.trend_rotation import generate_target_weights
from research.validation import run_research_backtest
from research.factors import compute_factors, list_factors
from strategies.regime_breakout import evaluate_breakout_signal
from strategies.registry import get_strategy
from research.scanner import ScannerConfig, scan_universe
from strategies.long_short_backtest import LongShortBacktestConfig, run_long_short_backtest


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


def test_factor_engine_is_lookahead_safe_and_registered():
    dates = pd.date_range("2020-01-01", periods=300, freq="B")
    bars = pd.DataFrame({"close": np.linspace(100, 180, len(dates)), "volume": np.full(len(dates), 1000.0)}, index=dates)
    factors = compute_factors(bars, bars["close"])
    assert {"ret_20d", "volume_ratio_5d", "breakout_count_20d", "surge_count_20d", "crash_count_20d", "market_trend"} <= set(factors.columns)
    assert pd.isna(factors.iloc[0]["ret_20d"])
    assert len(list_factors("US")) >= 10


def test_regime_breakout_signal_separates_short_signal_from_short_execution():
    dates = pd.date_range("2020-01-01", periods=320, freq="B")
    bars = pd.DataFrame({"close": np.linspace(180, 100, len(dates)), "volume": np.full(len(dates), 1000.0)}, index=dates)
    signal = evaluate_breakout_signal(bars, pd.Series(np.linspace(180, 100, len(dates)), index=dates), "US", "TEST", shortable=False)
    assert signal["direction"] in {"SHORT", "FLAT"}
    assert signal["research_only"] is True
    if signal["direction"] == "SHORT":
        assert signal["short_executable"] is False


def test_s003_is_registered_as_signal_only_strategy():
    strategy = get_strategy("S-003")
    assert strategy.mode == "signal-only"
    assert strategy.production_eligible is False


def test_universe_scanner_returns_ranked_signals_and_respects_shortability():
    dates = pd.date_range("2020-01-01", periods=330, freq="B")
    benchmark = pd.Series(np.linspace(100, 150, len(dates)), index=dates)
    universe = {
        "LONG": pd.DataFrame({"close": np.linspace(100, 220, len(dates)), "volume": np.full(len(dates), 1000.0)}, index=dates),
        "SHORT": pd.DataFrame({"close": np.linspace(180, 90, len(dates)), "volume": np.full(len(dates), 1000.0)}, index=dates),
    }
    result = scan_universe(universe, benchmark, "US", {"SHORT": {"shortable": False}}, scanner_config=ScannerConfig(max_long_positions=1, max_short_positions=1))
    assert result["research_only"] is True
    assert len(result["signals"]) == 2
    short = next(item for item in result["signals"] if item["symbol"] == "SHORT")
    assert short["short_executable"] is False
    assert result["research_portfolio"]["short_exposure"] == 0


def test_long_short_backtest_models_borrow_cost_and_next_day_short_execution():
    dates = pd.date_range("2023-01-01", periods=30, freq="B")
    prices = pd.DataFrame({"A": np.linspace(100, 110, len(dates)), "B": np.linspace(100, 90, len(dates))}, index=dates)
    weights = pd.DataFrame(0.0, index=dates, columns=prices.columns)
    weights.loc[dates[5], "B"] = -0.5
    result = run_long_short_backtest(prices, weights, LongShortBacktestConfig(annual_borrow_bps=1200), shortable={"B": True})
    assert result.positions.loc[dates[5], "B"] == 0
    assert result.positions.loc[dates[6], "B"] < 0
    assert result.metrics["borrow_cost_drag"] > 0


def test_long_short_backtest_rejects_unavailable_borrow():
    dates = pd.date_range("2023-01-01", periods=10, freq="B")
    prices = pd.DataFrame({"A": np.linspace(100, 90, len(dates))}, index=dates)
    weights = pd.DataFrame(-0.2, index=dates, columns=["A"])
    try:
        run_long_short_backtest(prices, weights)
    except ValueError as exc:
        assert "borrow availability" in str(exc)
    else:
        raise AssertionError("expected unavailable borrow to be rejected")
