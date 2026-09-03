from decimal import Decimal

import pandas as pd

import server.app as app_module
from pio_core import PioStore


def test_api_import_portfolio_and_health(tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, "store", PioStore(str(tmp_path / "api.db")))
    paths = app_module.app.openapi()["paths"]
    assert {"/api/health", "/api/accounts/import", "/api/portfolio", "/api/order-intents", "/api/audit", "/api/market-data/quotes", "/api/research/backtest", "/api/research/backtest/long-short", "/api/research/factors", "/api/research/market-rules", "/api/research/datasets/ohlcv/validate", "/api/research/experiments/personal", "/api/research/experiments/personal/run", "/api/research/signals/breakout", "/api/research/signals/breakout/universe", "/api/goai/audit-demo", "/api/execution/status", "/api/order-intents/{intent_id}/submit", "/api/order-intents/{intent_id}/sync"} <= set(paths)
    assert app_module.health()["execution"] == "paper-only"
    request = app_module.HoldingsImportRequest.model_validate(
        {
            "holdings": [
                {"symbol": "AAPL", "name": "Apple", "market": "US", "currency": "USD", "quantity": "2", "avg_cost": "200", "last_price": "225", "market_value": "450", "asset_type": "STOCK"},
                {"symbol": "CASH_USD", "name": "USD Cash", "market": "US", "currency": "USD", "quantity": "1000", "avg_cost": "1", "last_price": "1", "market_value": "1000", "asset_type": "CASH"},
            ],
            "fx_rates": {"USD/CNY": "7.2"},
            "source_name": "api-test.csv",
            "as_of": "2026-08-02",
        }
    )
    imported = app_module.import_holdings(request)
    assert imported["positions"] == 2
    portfolio = app_module.portfolio()
    assert len(portfolio["positions"]) == 2
    assert Decimal(portfolio["total_base_value"]) == Decimal("10440.0")
    assert app_module.audit()["verified"] is True


def test_goai_demo_is_blocked_without_creating_an_order(tmp_path, monkeypatch):
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    monkeypatch.setattr(app_module, "store", PioStore(str(tmp_path / "goai.db")))
    audit_before = app_module.audit()["events"]

    result = app_module.goai_audit_demo(app_module.GoaiAuditRequest())

    assert result["verdict"] == "BLOCKED"
    assert result["order_intent_created"] is False
    assert result["planner"]["mode"] == "RULE_FALLBACK"
    assert "未调用 Qwen" in result["planner"]["label"]
    assert result["evidence"]["dataset"]["kind"] == "SYNTHETIC_DEMO"
    assert result["evidence"]["backtest"]["walk_forward_folds"] == 5
    assert any(check["status"] == "BLOCKED" for check in result["evidence"]["risk_gate"]["checks"])

    # The gate decision itself is now appended to the immutable decision ledger.
    audit_after = app_module.audit()
    assert audit_after["verified"] is True
    assert len(audit_after["events"]) == len(audit_before) + 1
    event = audit_after["events"][0]
    assert event["event_type"] == "GUARDRAIL_RUN"
    assert event["entity_id"] == result["run_id"]


def test_guardrail_audit_endpoints_verify_chain(tmp_path, monkeypatch):
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    monkeypatch.setattr(app_module, "store", PioStore(str(tmp_path / "guardrail-api.db")))
    app_module.goai_audit_demo(app_module.GoaiAuditRequest())
    app_module.goai_audit_demo(app_module.GoaiAuditRequest())

    verified = app_module.verify_audit_chain()
    assert verified["verified"] is True
    assert verified["count"] == 2

    decisions = app_module.audit_guardrail()["decisions"]
    assert len(decisions) == 2
    assert {decision["event_type"] for decision in decisions} == {"GUARDRAIL_RUN"}


def test_breakout_signal_api_returns_structured_factor_evidence():
    dates = [item.date().isoformat() for item in pd.bdate_range("2024-01-01", periods=330)]
    close = [100 + index * 0.1 for index in range(len(dates))]
    volume = [1000.0 for _ in dates]
    request = app_module.BreakoutSignalRequest(symbol="TEST", market="US", dates=dates, close=close, volume=volume, benchmark_close=close)
    result = app_module.research_breakout_signal(request)
    assert result["strategy_id"] == "S-003"
    assert "volume_ratio_5d" in result["factors"]
    assert result["research_only"] is True


def test_market_rules_and_ohlcv_validation_api():
    rules = app_module.research_market_rules()
    assert {item["market"] for item in rules["rules"]} == {"CN", "US"}
    csv = "date,symbol,open,high,low,close,volume\n2024-01-01,AAA,10,11,9,10.5,100\n"
    report = app_module.validate_ohlcv_dataset(app_module.OhlcvValidationRequest(csv_text=csv))
    assert report["errors"] == []
    assert report["dataset_kind"] == "REAL_MARKET_DATA"
    assert report["data_fingerprint"]


def test_personal_experiment_api_is_not_an_execution_signal():
    result = app_module.personal_investment_experiment()
    assert result["verdict"] == "RESEARCH_ONLY"
    assert result["protocol"]["execution_mode"].startswith("research-only")


def test_personal_experiment_csv_api_replays_fixed_protocol():
    dates = pd.bdate_range("2021-01-04", periods=650)
    rows = []
    for symbol, drift in (("AAPL", 0.0004), ("600000", 0.0002)):
        close = 100 * (1 + drift) ** pd.Series(range(len(dates)), index=dates)
        for date, value in close.items():
            rows.append(f"{date.date()},{symbol},{value:.6f},{value * 1.01:.6f},{value * .99:.6f},{value:.6f},1000,{value:.6f},USD,US")
    csv = "date,symbol,open,high,low,close,volume,adjusted_close,currency,market\n" + "\n".join(rows)
    result = app_module.run_personal_investment_experiment_from_csv(
        app_module.PersonalExperimentRequest(csv_text=csv, benchmark_symbol="AAPL")
    )
    assert result["experiment_id"] == "PIO-EXP-001"
    assert result["protocol"]["benchmark"] == "AAPL buy-and-hold"
    assert result["input_dataset"]["data_fingerprint"]
    assert result["verdict"] == "NOT_READY"
