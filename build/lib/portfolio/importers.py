"""Normalize broker CSV exports into multi-market portfolio records.

This module deliberately does not fetch prices or FX rates. Callers must provide
explicit rates so historical imports remain reproducible and auditable.
"""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Dict, Iterable, List, Mapping, Optional, Union


@dataclass(frozen=True)
class Holding:
    symbol: str
    name: str
    market: str
    currency: str
    quantity: Decimal
    average_cost: Optional[Decimal]
    last_price: Optional[Decimal]
    market_value: Decimal
    asset_type: str

    def base_value(self, fx_rates: Mapping[str, Decimal], base_currency: str = "CNY") -> Decimal:
        if self.currency == base_currency:
            return self.market_value
        pair = f"{self.currency}/{base_currency}"
        if pair not in fx_rates:
            raise ValueError(f"missing explicit FX rate: {pair}")
        return self.market_value * fx_rates[pair]


@dataclass(frozen=True)
class Transaction:
    date: str
    symbol: str
    name: str
    market: str
    currency: str
    side: str
    quantity: Decimal
    price: Decimal
    fee: Decimal


@dataclass(frozen=True)
class ImportResult:
    schema: str
    holdings: List[Holding]
    transactions: List[Transaction]
    warnings: List[str]


ALIASES: Dict[str, Iterable[str]] = {
    "symbol": ("symbol", "ticker", "code", "证券代码", "股票代码", "代码"),
    "name": ("name", "security_name", "stock_name", "证券名称", "股票名称", "名称"),
    "market": ("market", "exchange", "市场", "交易所"),
    "currency": ("currency", "ccy", "币种", "货币"),
    "quantity": ("quantity", "qty", "position", "shares", "持仓数量", "数量", "股数"),
    "average_cost": ("avg_cost", "average_cost", "cost_basis", "成本价", "平均成本", "持仓成本"),
    "last_price": ("last_price", "market_price", "price", "当前价", "市价", "最新价"),
    "market_value": ("market_value", "value", "市值", "市场价值"),
    "asset_type": ("asset_type", "type", "security_type", "资产类型", "品种"),
    "date": ("date", "trade_date", "datetime", "成交日期", "交易日期", "日期"),
    "side": ("side", "action", "buy_or_sell", "买卖方向", "方向"),
    "fee": ("fee", "commission", "fees", "手续费", "佣金"),
}

LOOKUP = {
    re.sub(r"[\s_\-./()]", "", alias).lower(): target
    for target, aliases in ALIASES.items()
    for alias in aliases
}


def import_account_csv(source: Union[str, io.TextIOBase]) -> ImportResult:
    """Import holdings or transactions from CSV text or a text stream."""
    stream = io.StringIO(source.lstrip("\ufeff")) if isinstance(source, str) else source
    reader = csv.DictReader(stream)
    if not reader.fieldnames:
        raise ValueError("CSV is missing a header row")
    column_map = {header: LOOKUP.get(_normalize_header(header)) for header in reader.fieldnames}
    if "symbol" not in column_map.values():
        raise ValueError("CSV is missing a symbol/证券代码 column")
    schema = "transactions" if {"side", "date"}.intersection(column_map.values()) else "holdings"
    holdings: List[Holding] = []
    transactions: List[Transaction] = []
    warnings: List[str] = []

    for line_number, source_row in enumerate(reader, start=2):
        row = {target: source_row.get(header, "") for header, target in column_map.items() if target}
        try:
            if schema == "holdings":
                holdings.append(_holding(row))
            else:
                transactions.append(_transaction(row))
        except ValueError as exc:
            warnings.append(f"line {line_number}: {exc}")
    if not holdings and not transactions:
        raise ValueError("CSV contains no valid account records")
    return ImportResult(schema, holdings, transactions, warnings)


def _holding(row: Mapping[str, str]) -> Holding:
    symbol = _required(row, "symbol").upper()
    market = _market(symbol, row.get("market", ""))
    currency = (row.get("currency") or {"US": "USD", "HK": "HKD"}.get(market, "CNY")).upper()
    quantity = _decimal(_required(row, "quantity"), "quantity")
    last_price = _optional_decimal(row.get("last_price"))
    supplied_value = _optional_decimal(row.get("market_value"))
    if supplied_value is None and last_price is None:
        raise ValueError("holding needs last_price or market_value")
    market_value = supplied_value if supplied_value is not None else quantity * last_price  # type: ignore[operator]
    name = (row.get("name") or symbol).strip()
    asset_type = (row.get("asset_type") or ("CASH" if re.search(r"CASH|现金|货币", f"{symbol}{name}", re.I) else "STOCK")).upper()
    return Holding(symbol, name, market, currency, quantity, _optional_decimal(row.get("average_cost")), last_price, market_value, asset_type)


def _transaction(row: Mapping[str, str]) -> Transaction:
    symbol = _required(row, "symbol").upper()
    market = _market(symbol, row.get("market", ""))
    currency = (row.get("currency") or {"US": "USD", "HK": "HKD"}.get(market, "CNY")).upper()
    side_raw = _required(row, "side").upper()
    side = "BUY" if side_raw in {"BUY", "B", "买", "买入"} else "SELL" if side_raw in {"SELL", "S", "卖", "卖出"} else side_raw
    if side not in {"BUY", "SELL"}:
        raise ValueError(f"unsupported side: {side_raw}")
    return Transaction(
        _required(row, "date"), symbol, (row.get("name") or symbol).strip(), market, currency, side,
        _decimal(_required(row, "quantity"), "quantity"),
        _decimal(_required(row, "last_price"), "price"),
        _optional_decimal(row.get("fee")) or Decimal("0"),
    )


def _normalize_header(value: str) -> str:
    return re.sub(r"[\s_\-./()]", "", (value or "").lstrip("\ufeff")).lower()


def _required(row: Mapping[str, str], key: str) -> str:
    value = str(row.get(key, "")).strip()
    if not value:
        raise ValueError(f"missing {key}")
    return value


def _decimal(value: str, label: str) -> Decimal:
    try:
        return Decimal(str(value).replace(",", "").replace("¥", "").replace("￥", "").replace("$", "").strip())
    except InvalidOperation as exc:
        raise ValueError(f"invalid {label}: {value}") from exc


def _optional_decimal(value: Optional[str]) -> Optional[Decimal]:
    if value is None or not str(value).strip():
        return None
    return _decimal(str(value), "number")


def _market(symbol: str, raw: str) -> str:
    market = (raw or "").upper()
    if re.search(r"US|NASDAQ|NYSE|AMEX", market):
        return "US"
    if re.search(r"HK|SEHK|港", market):
        return "HK"
    if re.search(r"CN|SSE|SZSE|SH|SZ|沪|深|中国", market):
        return "CN"
    if re.fullmatch(r"\d{5}(\.HK)?", symbol, re.I):
        return "HK"
    if re.fullmatch(r"\d{6}(\.(SH|SZ))?", symbol, re.I):
        return "CN"
    return "US"
