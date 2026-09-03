import io

import numpy as np
import pandas as pd
import pytest

from execution.market_rules import get_market_rules
from research.datasets import load_ohlcv_csv, validate_ohlcv_frame
from strategies.long_short_backtest import LongShortBacktestConfig, run_long_short_backtest


def test_market_rules_distinguish_cn_and_us():
    cn = get_market_rules("CN")
    us = get_market_rules("US")
    assert cn.lot_size == 100
    assert cn.supports_short is False
    assert cn.daily_price_limit_pct == 0.10
    assert us.lot_size == 1
    assert us.daily_price_limit_pct is None


def test_cn_long_short_backtest_rejects_stock_shorting():
    dates = pd.date_range("2024-01-01", periods=5, freq="B")
    prices = pd.DataFrame({"600000": np.linspace(10, 9, len(dates))}, index=dates)
    weights = pd.DataFrame(-0.2, index=dates, columns=prices.columns)
    with pytest.raises(ValueError, match="do not permit"):
        run_long_short_backtest(prices, weights, market="CN", shortable={"600000": True})


def test_cn_price_limit_blocks_buy_and_reports_day():
    dates = pd.date_range("2024-01-01", periods=4, freq="B")
    prices = pd.DataFrame({"600000": [10.0, 11.0, 11.0, 11.0]}, index=dates)
    weights = pd.DataFrame(0.0, index=dates, columns=prices.columns)
    weights.loc[dates[0], "600000"] = 0.5
    result = run_long_short_backtest(prices, weights, market="CN")
    assert bool(result.blocked_trade_days.loc[dates[1]]) is True
    assert result.positions.loc[dates[1], "600000"] == 0


def test_ohlcv_contract_rejects_duplicate_and_bad_ohlc():
    frame = pd.DataFrame(
        [
            {"date": "2024-01-01", "symbol": "A", "open": 10, "high": 9, "low": 8, "close": 10, "volume": 100},
            {"date": "2024-01-01", "symbol": "A", "open": 10, "high": 11, "low": 9, "close": 10, "volume": 100},
        ]
    )
    report = validate_ohlcv_frame(frame)
    assert report["errors"]
    assert any("duplicate" in item for item in report["errors"])
    assert any("OHLC" in item for item in report["errors"])


def test_ohlcv_csv_load_is_sorted_and_fingerprinted():
    csv = io.StringIO(
        "date,symbol,open,high,low,close,volume,adjusted_close,currency,market\n"
        "2024-01-02,A,10,11,9,10.5,100,10.5,USD,US\n"
        "2024-01-01,A,9,10,8,9.5,120,9.5,USD,US\n"
    )
    frame, report = load_ohlcv_csv(csv)
    assert frame.iloc[0]["date"] == pd.Timestamp("2024-01-01")
    assert report["data_fingerprint"]
    assert report["errors"] == []
