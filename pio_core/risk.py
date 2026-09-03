"""Deterministic hard-risk policy. LLMs and agents cannot override this module."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Dict, Iterable, List, Mapping

from execution.market_rules import get_market_rules


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

    checks.append(_check("VALID_ORDER", quantity > 0 and reference_price > 0 and side in {"BUY", "SELL"}, "Order fields are valid", "Quantity, price or side is invalid"))
    checks.append(_check("ALLOWED_MARKET", market in {"CN", "US", "HK"}, f"Market {market} is allowed", f"Market {market} is not in the allowed list"))
    try:
        market_rule = get_market_rules(market)
    except ValueError:
        market_rule = None
    if market_rule is not None:
        # Mainland markets require board lots when opening/increasing a
        # position; selling an odd-lot remainder is permitted by many brokers.
        lot_valid = quantity > 0 and (side != "BUY" or quantity % Decimal(str(market_rule.lot_size)) == 0)
        checks.append(_check("LOT_SIZE", lot_valid, f"Quantity matches the {market_rule.market} {market_rule.lot_size}-share trading unit (selling odd-lot remainders excepted)", f"Buy quantity must be a multiple of the {market_rule.market} {market_rule.lot_size}-share trading unit"))
        short_requested = side in {"SELL_SHORT", "SHORT"}
        checks.append(_check("SHORT_PERMISSION", not short_requested or market_rule.supports_short, "Short selling is permitted by the market rules", f"{market_rule.market} market rules do not permit shorting this stock"))

    try:
        as_of = datetime.fromisoformat(snapshot_as_of.replace("Z", "+00:00")).date()
    except ValueError:
        as_of = date.min
    age = (date.today() - as_of).days
    checks.append(_check("DATA_FRESHNESS", 0 <= age <= max_snapshot_age_days, f"Account snapshot is {age} day(s) old", f"Account snapshot is stale or has an invalid date: {age} days"))

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
    checks.append(_check("ORDER_SIZE", total_base > 0 and order_base / total_base <= max_order_weight, f"Order is {(order_base / total_base if total_base else Decimal('0')):.1%} of the portfolio", f"Order exceeds the {max_order_weight:.0%} portfolio limit"))

    if side == "BUY":
        checks.append(_check("CASH_AVAILABLE", cash_available >= order_value, f"Available cash {cash_available} {currency}", f"Insufficient {currency} cash"))
        post_value = current_value_base + order_base
        checks.append(_check("POSITION_LIMIT", total_base > 0 and post_value / total_base <= max_single_weight, f"Post-trade single-position weight {(post_value / total_base if total_base else Decimal('0')):.1%}", f"Post-trade single-position weight exceeds {max_single_weight:.0%}"))
    else:
        checks.append(_check("POSITION_AVAILABLE", current_quantity >= quantity, f"Sellable quantity {current_quantity}", f"Insufficient holdings: only {current_quantity}"))

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
