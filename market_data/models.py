"""Normalized market-data domain models."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional


@dataclass(frozen=True)
class QuoteRequest:
    symbol: str
    market: str
    currency: str

    def normalized(self) -> "QuoteRequest":
        return QuoteRequest(self.symbol.strip().upper(), self.market.strip().upper(), self.currency.strip().upper())


@dataclass(frozen=True)
class Quote:
    symbol: str
    market: str
    currency: str
    price: Decimal
    timestamp: str
    source: str
    is_realtime: bool
    bid: Optional[Decimal] = None
    ask: Optional[Decimal] = None
    previous_close: Optional[Decimal] = None
    received_at: Optional[str] = None
    cache_age_seconds: float = 0.0

    def to_dict(self) -> dict[str, object]:
        return {
            "symbol": self.symbol,
            "market": self.market,
            "currency": self.currency,
            "price": str(self.price),
            "bid": None if self.bid is None else str(self.bid),
            "ask": None if self.ask is None else str(self.ask),
            "previous_close": None if self.previous_close is None else str(self.previous_close),
            "timestamp": self.timestamp,
            "received_at": self.received_at,
            "source": self.source,
            "is_realtime": self.is_realtime,
            "cache_age_seconds": round(self.cache_age_seconds, 3),
        }
