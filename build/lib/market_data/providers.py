"""Credentialed HTTP market-data providers.

The adapters use documented vendor APIs. They deliberately do not scrape web
pages, and they never silently downgrade delayed data to real-time data.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from decimal import Decimal
from typing import Callable, Iterable, Mapping, Optional
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .models import Quote, QuoteRequest


JsonTransport = Callable[[str, str, Mapping[str, str], Optional[dict[str, object]], float], dict[str, object]]


def default_json_transport(
    method: str,
    url: str,
    headers: Mapping[str, str],
    body: Optional[dict[str, object]],
    timeout: float,
) -> dict[str, object]:
    payload = None if body is None else json.dumps(body).encode("utf-8")
    request = Request(url, data=payload, method=method, headers=dict(headers))
    with urlopen(request, timeout=timeout) as response:  # noqa: S310 - URLs are fixed provider endpoints.
        return json.loads(response.read().decode("utf-8"))


class AlpacaMarketDataProvider:
    """US equity snapshots from Alpaca's official Market Data API."""

    name = "alpaca"
    markets = frozenset({"US"})
    is_realtime = True

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        feed: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: float = 8.0,
        transport: JsonTransport = default_json_transport,
    ):
        self.api_key = api_key or os.getenv("ALPACA_API_KEY_ID", "")
        self.api_secret = api_secret or os.getenv("ALPACA_API_SECRET_KEY", "")
        self.feed = feed or os.getenv("ALPACA_MARKET_DATA_FEED", "iex")
        self.base_url = (base_url or os.getenv("ALPACA_MARKET_DATA_URL", "https://data.alpaca.markets")).rstrip("/")
        self.timeout = timeout
        self.transport = transport

    @property
    def configured(self) -> bool:
        return bool(self.api_key and self.api_secret)

    def fetch_quotes(self, instruments: Iterable[QuoteRequest]) -> list[Quote]:
        requests = [item.normalized() for item in instruments]
        if not self.configured:
            raise RuntimeError("Alpaca market data is not configured")
        if any(item.market != "US" for item in requests):
            raise ValueError("Alpaca market-data adapter only supports US equities")
        symbols = sorted({item.symbol for item in requests})
        query = urlencode({"symbols": ",".join(symbols), "feed": self.feed})
        payload = self.transport(
            "GET",
            f"{self.base_url}/v2/stocks/snapshots?{query}",
            {"APCA-API-KEY-ID": self.api_key, "APCA-API-SECRET-KEY": self.api_secret, "Accept": "application/json"},
            None,
            self.timeout,
        )
        snapshots = payload.get("snapshots", payload)
        if not isinstance(snapshots, dict):
            raise RuntimeError("Alpaca returned an invalid snapshots payload")
        received_at = _now()
        output: list[Quote] = []
        currencies = {item.symbol: item.currency for item in requests}
        for symbol in symbols:
            raw = snapshots.get(symbol)
            if not isinstance(raw, dict):
                continue
            trade = raw.get("latestTrade") or {}
            quote = raw.get("latestQuote") or {}
            daily = raw.get("dailyBar") or {}
            previous = raw.get("prevDailyBar") or {}
            price = _decimal_or_none(trade.get("p")) or _decimal_or_none(daily.get("c"))
            if price is None:
                continue
            output.append(
                Quote(
                    symbol=symbol,
                    market="US",
                    currency=currencies.get(symbol, "USD"),
                    price=price,
                    bid=_decimal_or_none(quote.get("bp")),
                    ask=_decimal_or_none(quote.get("ap")),
                    previous_close=_decimal_or_none(previous.get("c")),
                    timestamp=str(trade.get("t") or daily.get("t") or received_at),
                    received_at=received_at,
                    source=f"alpaca:{self.feed}",
                    is_realtime=True,
                )
            )
        return output


class TushareRealtimeProvider:
    """A-share real-time quote adapter using TuShare Pro's ``rt_k`` API."""

    name = "tushare"
    markets = frozenset({"CN"})
    is_realtime = True

    def __init__(
        self,
        token: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: float = 8.0,
        transport: JsonTransport = default_json_transport,
    ):
        self.token = token or os.getenv("TUSHARE_TOKEN", "")
        self.base_url = base_url or os.getenv("TUSHARE_API_URL", "https://api.tushare.pro")
        self.timeout = timeout
        self.transport = transport

    @property
    def configured(self) -> bool:
        return bool(self.token)

    def fetch_quotes(self, instruments: Iterable[QuoteRequest]) -> list[Quote]:
        requests = [item.normalized() for item in instruments]
        if not self.configured:
            raise RuntimeError("TuShare real-time data is not configured")
        if any(item.market != "CN" for item in requests):
            raise ValueError("TuShare real-time adapter currently supports CN equities only")
        code_map = {_to_tushare_code(item.symbol): item for item in requests}
        payload = self.transport(
            "POST",
            self.base_url,
            {"Content-Type": "application/json", "Accept": "application/json"},
            {"api_name": "rt_k", "token": self.token, "params": {"ts_code": ",".join(code_map)}, "fields": ""},
            self.timeout,
        )
        if payload.get("code") not in (None, 0):
            raise RuntimeError(f"TuShare error {payload.get('code')}: {payload.get('msg', 'unknown error')}")
        data = payload.get("data") or {}
        fields = data.get("fields") or []
        rows = data.get("items") or []
        received_at = _now()
        output: list[Quote] = []
        for values in rows:
            row = dict(zip(fields, values))
            code = str(row.get("ts_code") or row.get("code") or "").upper()
            item = code_map.get(code) or code_map.get(_to_tushare_code(code))
            if item is None:
                continue
            price = _first_decimal(row, "price", "close", "trade")
            if price is None:
                continue
            trade_time = row.get("trade_time") or row.get("time") or received_at
            trade_date = row.get("trade_date") or row.get("date")
            timestamp = f"{trade_date}T{trade_time}" if trade_date and "T" not in str(trade_time) else str(trade_time)
            output.append(
                Quote(
                    symbol=item.symbol,
                    market="CN",
                    currency=item.currency or "CNY",
                    price=price,
                    bid=_first_decimal(row, "bid", "bid1"),
                    ask=_first_decimal(row, "ask", "ask1"),
                    previous_close=_first_decimal(row, "pre_close", "prev_close"),
                    timestamp=timestamp,
                    received_at=received_at,
                    source="tushare:rt_k",
                    is_realtime=True,
                )
            )
        return output


def _to_tushare_code(symbol: str) -> str:
    normalized = symbol.upper().replace(".SH", "").replace(".SZ", "").replace(".BJ", "")
    if "." in symbol:
        return symbol.upper()
    if normalized.startswith(("4", "8")):
        return f"{normalized}.BJ"
    if normalized.startswith(("5", "6", "9")):
        return f"{normalized}.SH"
    return f"{normalized}.SZ"


def _first_decimal(row: Mapping[str, object], *keys: str) -> Optional[Decimal]:
    for key in keys:
        value = _decimal_or_none(row.get(key))
        if value is not None:
            return value
    return None


def _decimal_or_none(value: object) -> Optional[Decimal]:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except Exception:
        return None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
