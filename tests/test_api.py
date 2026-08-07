from decimal import Decimal

import server.app as app_module
from pio_core import PioStore


def test_api_import_portfolio_and_health(tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, "store", PioStore(str(tmp_path / "api.db")))
    paths = app_module.app.openapi()["paths"]
    assert {"/api/health", "/api/accounts/import", "/api/portfolio", "/api/order-intents", "/api/audit", "/api/market-data/quotes", "/api/research/backtest", "/api/goai/audit-demo", "/api/execution/status", "/api/order-intents/{intent_id}/submit"} <= set(paths)
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
    assert app_module.audit()["events"] == audit_before
