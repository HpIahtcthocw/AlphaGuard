"""Environment locks and idempotent external order submission."""

from __future__ import annotations

import os
from decimal import Decimal
from typing import Mapping, Optional

from .brokers import AlpacaTradingBroker


LIVE_UNLOCK_VALUE = "I_ACCEPT_REAL_MONEY_RISK"


class ExecutionService:
    def __init__(self, adapter_name: Optional[str] = None, broker=None):
        self.adapter_name = adapter_name or os.getenv("PIO_EXECUTION_ADAPTER", "local-paper")
        if broker is not None:
            self.broker = broker
        elif self.adapter_name == "alpaca-paper":
            self.broker = AlpacaTradingBroker("paper")
        elif self.adapter_name == "alpaca-live":
            self.broker = AlpacaTradingBroker("live")
        else:
            self.broker = None

    def status(self) -> dict[str, object]:
        return {
            "adapter": self.adapter_name,
            "external_submission_enabled": self.broker is not None,
            "configured": bool(self.broker and self.broker.configured),
            "environment": getattr(self.broker, "environment", "local"),
            "markets": sorted(getattr(self.broker, "markets", [])),
            "live_unlocked": self._live_unlocked(),
            "requires_human_approval": True,
            "kill_switch": self.adapter_name == "local-paper",
        }

    def submit(
        self,
        intent: Mapping[str, object],
        confirmation_phrase: str,
        market_price: Decimal,
        max_price_deviation: Decimal = Decimal("0.05"),
    ) -> dict[str, object]:
        if self.broker is None:
            raise ValueError("external broker submission is disabled; use local paper simulation")
        if not self.broker.configured:
            raise ValueError("external broker credentials are not configured")
        if str(intent["status"]) != "APPROVED":
            raise ValueError("only an approved order intent can be submitted")
        expected = f"SUBMIT {intent['id']}"
        if confirmation_phrase != expected:
            raise ValueError(f"confirmation phrase must exactly equal: {expected}")
        if self.broker.is_live and not self._live_unlocked():
            raise ValueError("live trading is locked by the environment kill switch")
        reference = Decimal(str(intent["reference_price"]))
        if reference <= 0 or market_price <= 0:
            raise ValueError("reference and market prices must be positive")
        deviation = abs(market_price / reference - Decimal("1"))
        if deviation > max_price_deviation:
            raise ValueError(f"live quote deviates {deviation:.2%} from the approved reference price")
        return self.broker.submit_order(intent)

    def _live_unlocked(self) -> bool:
        if not self.broker or not self.broker.is_live:
            return False
        return os.getenv("PIO_LIVE_TRADING_UNLOCK", "") == LIVE_UNLOCK_VALUE
