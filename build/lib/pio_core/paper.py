"""Paper execution uses the same order intent fields that future adapters consume."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP


@dataclass(frozen=True)
class PaperFill:
    fill_price: Decimal
    quantity: Decimal
    fee: Decimal
    gross_value: Decimal


def simulate_fill(
    side: str,
    quantity: Decimal,
    reference_price: Decimal,
    commission_bps: Decimal = Decimal("3"),
    slippage_bps: Decimal = Decimal("5"),
) -> PaperFill:
    if quantity <= 0 or reference_price <= 0:
        raise ValueError("paper fill requires positive quantity and price")
    if side.upper() not in {"BUY", "SELL"}:
        raise ValueError(f"unsupported paper side: {side}")
    direction = Decimal("1") if side.upper() == "BUY" else Decimal("-1")
    fill_price = reference_price * (Decimal("1") + direction * slippage_bps / Decimal("10000"))
    fill_price = fill_price.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    gross = (quantity * fill_price).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    fee = (gross * commission_bps / Decimal("10000")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return PaperFill(fill_price, quantity, fee, gross)
