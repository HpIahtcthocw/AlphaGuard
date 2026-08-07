from decimal import Decimal

import pytest

from execution.brokers import AlpacaTradingBroker
from execution.service import ExecutionService


def approved_intent():
    return {
        "id": "intent-1",
        "symbol": "AAPL",
        "market": "US",
        "currency": "USD",
        "side": "BUY",
        "quantity": "2",
        "reference_price": "225",
        "status": "APPROVED",
        "idempotency_key": "client-plan-1",
    }


def test_alpaca_paper_submission_requires_exact_confirmation_and_maps_order():
    captured = {}

    def transport(method, url, headers, body, timeout):
        captured.update(body)
        return {"id": "alpaca-123", "status": "accepted", "submitted_at": "2026-08-02T10:00:00Z"}

    broker = AlpacaTradingBroker("paper", "key", "secret", transport=transport)
    service = ExecutionService("alpaca-paper", broker)
    with pytest.raises(ValueError, match="confirmation phrase"):
        service.submit(approved_intent(), "yes", Decimal("225.2"))
    result = service.submit(approved_intent(), "SUBMIT intent-1", Decimal("225.2"))
    assert result["external_order_id"] == "alpaca-123"
    assert captured["client_order_id"] == "client-plan-1"
    assert captured["type"] == "market"


def test_external_submission_rejects_large_quote_deviation():
    broker = AlpacaTradingBroker("paper", "key", "secret", transport=lambda *args: {"id": "unused"})
    service = ExecutionService("alpaca-paper", broker)
    with pytest.raises(ValueError, match="deviates"):
        service.submit(approved_intent(), "SUBMIT intent-1", Decimal("250"))


def test_live_broker_is_locked_without_environment_unlock(monkeypatch):
    monkeypatch.delenv("PIO_LIVE_TRADING_UNLOCK", raising=False)
    broker = AlpacaTradingBroker("live", "key", "secret", transport=lambda *args: {"id": "unused"})
    service = ExecutionService("alpaca-live", broker)
    with pytest.raises(ValueError, match="kill switch"):
        service.submit(approved_intent(), "SUBMIT intent-1", Decimal("225"))
