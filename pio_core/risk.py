"""Deterministic hard-risk policy. LLMs and agents cannot override this module."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Dict, Iterable, List, Mapping


@dataclass(frozen=True)
class RiskCheck:
    code: str
    status: str
    message: str


@dataclass(frozen=True)
class RiskDecision:
    status: str
    checks: List[RiskCheck]


def evaluate_order(
    positions: Iterable[Mapping[str, object]],
    fx_rates: Mapping[str, Decimal],
    snapshot_as_of: str,
    symbol: str,
    market: str,
    currency: str,
    side: str,
    quantity: Decimal,
    reference_price: Decimal,
    max_single_weight: Decimal = Decimal("0.40"),
    max_order_weight: Decimal = Decimal("0.20"),
    max_snapshot_age_days: int = 7,
) -> RiskDecision:
    checks: List[RiskCheck] = []
    position_list = list(positions)
    side = side.upper()
    market = market.upper()
    currency = currency.upper()

    checks.append(_check("VALID_ORDER", quantity > 0 and reference_price > 0 and side in {"BUY", "SELL"}, "订单字段有效", "数量、价格或方向无效"))
    checks.append(_check("ALLOWED_MARKET", market in {"CN", "US", "HK"}, f"市场 {market} 已允许", f"市场 {market} 未列入允许范围"))

    try:
        as_of = datetime.fromisoformat(snapshot_as_of.replace("Z", "+00:00")).date()
    except ValueError:
        as_of = date.min
    age = (date.today() - as_of).days
    checks.append(_check("DATA_FRESHNESS", 0 <= age <= max_snapshot_age_days, f"账户快照距今 {age} 天", f"账户快照已过期或日期异常：{age} 天"))

    total_base = Decimal("0")
    current_value_base = Decimal("0")
    current_quantity = Decimal("0")
    cash_available = Decimal("0")
    for position in position_list:
        position_currency = str(position["currency"])
        value = Decimal(str(position["market_value"]))
        base_value = _convert(value, position_currency, fx_rates)
        total_base += base_value
        if str(position["symbol"]) == symbol:
            current_value_base = base_value
            current_quantity = Decimal(str(position["quantity"]))
        if str(position.get("asset_type")) == "CASH" and position_currency == currency:
            cash_available += value

    order_value = quantity * reference_price
    order_base = _convert(order_value, currency, fx_rates)
    checks.append(_check("ORDER_SIZE", total_base > 0 and order_base / total_base <= max_order_weight, f"订单占组合 {(order_base / total_base if total_base else Decimal('0')):.1%}", f"订单超过组合 {max_order_weight:.0%} 上限"))

    if side == "BUY":
        checks.append(_check("CASH_AVAILABLE", cash_available >= order_value, f"可用现金 {cash_available} {currency}", f"{currency} 现金不足"))
        post_value = current_value_base + order_base
        checks.append(_check("POSITION_LIMIT", total_base > 0 and post_value / total_base <= max_single_weight, f"交易后单项权重 {(post_value / total_base if total_base else Decimal('0')):.1%}", f"交易后单项权重超过 {max_single_weight:.0%}"))
    else:
        checks.append(_check("POSITION_AVAILABLE", current_quantity >= quantity, f"可卖数量 {current_quantity}", f"持仓不足：仅有 {current_quantity}"))

    status = "PASS" if all(check.status == "PASS" for check in checks) else "FAIL"
    return RiskDecision(status, checks)


def _convert(value: Decimal, currency: str, fx_rates: Mapping[str, Decimal], base: str = "CNY") -> Decimal:
    if currency == base:
        return value
    pair = f"{currency}/{base}"
    if pair not in fx_rates:
        raise ValueError(f"missing FX rate {pair}")
    return value * fx_rates[pair]


def _check(code: str, passed: bool, success: str, failure: str) -> RiskCheck:
    return RiskCheck(code, "PASS" if passed else "FAIL", success if passed else failure)
