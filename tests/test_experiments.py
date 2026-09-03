import pandas as pd

from research.experiments import EXPERIMENT_ID, build_personal_experiment_prices, ohlcv_to_close_prices, run_personal_investment_experiment


def test_personal_experiment_is_deterministic_and_research_only():
    first = build_personal_experiment_prices()
    second = build_personal_experiment_prices()
    assert first.equals(second)
    report = run_personal_investment_experiment(first)
    assert report["experiment_id"] == EXPERIMENT_ID
    assert report["verdict"] == "RESEARCH_ONLY"
    assert report["protocol"]["execution_mode"].startswith("research-only")
    assert any(gate["code"] == "DATA_PROVENANCE" and gate["status"] == "BLOCKED" for gate in report["gates"])
    assert report["evidence"]["walk_forward"]["folds"]


def test_ohlcv_to_close_prices_prefers_complete_adjusted_close():
    frame = pd.DataFrame(
        [
            {"date": "2024-01-01", "symbol": "A", "open": 10, "high": 11, "low": 9, "close": 10, "adjusted_close": 9.5, "volume": 100},
            {"date": "2024-01-01", "symbol": "B", "open": 20, "high": 21, "low": 19, "close": 20, "adjusted_close": 19.5, "volume": 100},
        ]
    )
    prices, note = ohlcv_to_close_prices(frame)
    assert note == "using complete adjusted_close"
    assert prices.loc[pd.Timestamp("2024-01-01"), "A"] == 9.5
