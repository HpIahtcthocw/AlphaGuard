from decimal import Decimal

import server.app as app_module
from pio_core import PioStore


def test_api_import_portfolio_and_health(tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, "store", PioStore(str(tmp_path / "api.db")))
    paths = app_module.app.openapi()["paths"]
    assert {"/api/health", "/api/accounts/import", "/api/portfolio", "/api/order-intents", "/api/audit", "/api/market-data/quotes", "/api/research/backtest", "/api/execution/status", "/api/order-intents/{intent_id}/submit"} <= set(paths)
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
