"""External broker adapters.

Adapters only translate already-approved deterministic order intents. They do
not create strategies, alter quantities, or bypass local risk checks.
"""

from __future__ import annotations

import json
import os
from typing import Mapping, Optional
from urllib.request import Request, urlopen


class AlpacaTradingBroker:
    name = "alpaca"
    markets = frozenset({"US"})

    def __init__(
        self,
        environment: str = "paper",
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: float = 10.0,
        transport=None,
    ):
        if environment not in {"paper", "live"}:
            raise ValueError("Alpaca environment must be paper or live")
        self.environment = environment
        self.api_key = api_key or os.getenv("ALPACA_API_KEY_ID", "")
        self.api_secret = api_secret or os.getenv("ALPACA_API_SECRET_KEY", "")
        default_url = "https://paper-api.alpaca.markets" if environment == "paper" else "https://api.alpaca.markets"
        self.base_url = (base_url or default_url).rstrip("/")
        self.timeout = timeout
        self.transport = transport or _default_transport

    @property
    def configured(self) -> bool:
        return bool(self.api_key and self.api_secret)

    @property
    def is_live(self) -> bool:
        return self.environment == "live"

    def submit_order(self, intent: Mapping[str, object]) -> dict[str, object]:
        if not self.configured:
            raise RuntimeError("Alpaca trading is not configured")
        if str(intent["market"]).upper() != "US":
            raise ValueError("Alpaca broker adapter only supports US orders")
        payload = {
            "symbol": str(intent["symbol"]).upper(),
            "qty": str(intent["quantity"]),
            "side": str(intent["side"]).lower(),
            "type": "market",
            "time_in_force": "day",
            "client_order_id": str(intent["idempotency_key"]),
            "extended_hours": False,
        }
        response = self.transport(
            "POST",
            f"{self.base_url}/v2/orders",
            {
                "APCA-API-KEY-ID": self.api_key,
                "APCA-API-SECRET-KEY": self.api_secret,
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            payload,
            self.timeout,
        )
        external_id = response.get("id")
        if not external_id:
            raise RuntimeError("broker response did not contain an order id")
        return {
            "external_order_id": str(external_id),
            "status": str(response.get("status") or "accepted").upper(),
            "submitted_at": str(response.get("submitted_at") or response.get("created_at") or ""),
            "raw": response,
        }


def _default_transport(method: str, url: str, headers: Mapping[str, str], body: dict[str, object], timeout: float) -> dict[str, object]:
    request = Request(url, data=json.dumps(body).encode("utf-8"), method=method, headers=dict(headers))
    with urlopen(request, timeout=timeout) as response:  # noqa: S310 - fixed broker endpoint.
        return json.loads(response.read().decode("utf-8"))
