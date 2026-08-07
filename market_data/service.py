"""Provider routing, TTL caching, and explicit snapshot fallback."""

from __future__ import annotations

import os
import threading
import time
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal
from typing import Callable, Iterable, Mapping, Protocol

from .models import Quote, QuoteRequest


class QuoteProvider(Protocol):
    name: str
    markets: frozenset[str]
    is_realtime: bool

    @property
    def configured(self) -> bool: ...

    def fetch_quotes(self, instruments: Iterable[QuoteRequest]) -> list[Quote]: ...


class PortfolioSnapshotProvider:
    """Non-real-time fallback using the latest imported portfolio snapshot."""

    name = "portfolio-snapshot"
    markets = frozenset({"CN", "US", "HK"})
    is_realtime = False
    configured = True

    def __init__(self, portfolio_loader: Callable[[str], Mapping[str, object]], account_id: str = "default"):
        self.portfolio_loader = portfolio_loader
        self.account_id = account_id

    def fetch_quotes(self, instruments: Iterable[QuoteRequest]) -> list[Quote]:
        portfolio = self.portfolio_loader(self.account_id)
        positions = portfolio.get("positions", [])
        indexed = {(str(item["symbol"]).upper(), str(item["market"]).upper()): item for item in positions}
        timestamp = str(portfolio.get("as_of") or datetime.now(timezone.utc).isoformat())
        received_at = datetime.now(timezone.utc).isoformat()
        output: list[Quote] = []
        for request in instruments:
            item = request.normalized()
            position = indexed.get((item.symbol, item.market))
            if not position or position.get("last_price") in (None, ""):
                continue
            output.append(
                Quote(
                    symbol=item.symbol,
                    market=item.market,
                    currency=item.currency,
                    price=Decimal(str(position["last_price"])),
                    previous_close=None,
                    timestamp=timestamp,
                    received_at=received_at,
                    source="portfolio-snapshot",
                    is_realtime=False,
                )
            )
        return output


class MarketDataService:
    def __init__(
        self,
        providers: Iterable[QuoteProvider],
        routes: Mapping[str, str],
        fallback_provider: QuoteProvider,
        ttl_seconds: float = 3.0,
    ):
        self.providers = {provider.name: provider for provider in providers}
        self.routes = {market.upper(): provider for market, provider in routes.items()}
        self.fallback_provider = fallback_provider
        self.ttl_seconds = max(float(ttl_seconds), 0.0)
        self._cache: dict[tuple[str, str, str], tuple[float, Quote]] = {}
        self._lock = threading.Lock()

    def status(self) -> dict[str, object]:
        providers = []
        for provider in [*self.providers.values(), self.fallback_provider]:
            providers.append(
                {
                    "name": provider.name,
                    "markets": sorted(provider.markets),
                    "configured": bool(provider.configured),
                    "is_realtime": provider.is_realtime,
                }
            )
        return {"routes": dict(self.routes), "cache_ttl_seconds": self.ttl_seconds, "providers": providers}

    def get_quotes(self, instruments: Iterable[QuoteRequest], allow_snapshot_fallback: bool = True) -> dict[str, object]:
        requests = [item.normalized() for item in instruments]
        if not requests:
            raise ValueError("at least one instrument is required")
        if len(requests) > 100:
            raise ValueError("a quote request is limited to 100 instruments")
        now = time.monotonic()
        found: dict[tuple[str, str, str], Quote] = {}
        pending: list[QuoteRequest] = []
        with self._lock:
            for item in requests:
                key = _key(item)
                cached = self._cache.get(key)
                if cached and now - cached[0] <= self.ttl_seconds:
                    found[key] = replace(cached[1], cache_age_seconds=now - cached[0])
                else:
                    pending.append(item)

        errors: list[dict[str, str]] = []
        grouped: dict[str, list[QuoteRequest]] = {}
        for item in pending:
            grouped.setdefault(self.routes.get(item.market, ""), []).append(item)
        unresolved: list[QuoteRequest] = []
        for provider_name, group in grouped.items():
            provider = self.providers.get(provider_name)
            if not provider or not provider.configured:
                unresolved.extend(group)
                errors.append({"provider": provider_name or "unrouted", "error": "provider is not configured", "symbols": ",".join(item.symbol for item in group)})
                continue
            try:
                quotes = provider.fetch_quotes(group)
                self._remember(quotes)
                quote_keys = {_key_quote(quote) for quote in quotes}
                for quote in quotes:
                    found[_key_quote(quote)] = quote
                unresolved.extend(item for item in group if _key(item) not in quote_keys)
            except Exception as exc:
                unresolved.extend(group)
                errors.append({"provider": provider.name, "error": str(exc), "symbols": ",".join(item.symbol for item in group)})

        if allow_snapshot_fallback and unresolved:
            try:
                quotes = self.fallback_provider.fetch_quotes(unresolved)
                for quote in quotes:
                    found[_key_quote(quote)] = quote
                quote_keys = {_key_quote(quote) for quote in quotes}
                unresolved = [item for item in unresolved if _key(item) not in quote_keys]
            except Exception as exc:
                errors.append({"provider": self.fallback_provider.name, "error": str(exc), "symbols": ",".join(item.symbol for item in unresolved)})

        for item in unresolved:
            errors.append({"provider": self.routes.get(item.market, "unrouted"), "error": "quote unavailable", "symbols": item.symbol})
        ordered = [found[_key(item)].to_dict() for item in requests if _key(item) in found]
        return {"quotes": ordered, "errors": errors, "requested": len(requests), "returned": len(ordered)}

    def _remember(self, quotes: Iterable[Quote]) -> None:
        now = time.monotonic()
        with self._lock:
            for quote in quotes:
                self._cache[_key_quote(quote)] = (now, quote)


def routes_from_env() -> dict[str, str]:
    routes = {"US": "alpaca", "CN": "tushare"}
    raw = os.getenv("PIO_MARKET_DATA_ROUTES", "")
    for item in raw.split(","):
        if "=" not in item:
            continue
        market, provider = item.split("=", 1)
        if market.strip() and provider.strip():
            routes[market.strip().upper()] = provider.strip()
    return routes


def _key(request: QuoteRequest) -> tuple[str, str, str]:
    return request.symbol, request.market, request.currency


def _key_quote(quote: Quote) -> tuple[str, str, str]:
    return quote.symbol.upper(), quote.market.upper(), quote.currency.upper()
