"""Market-specific trading constraints used by research and execution gates.

These rules intentionally model the common denominator of a market. They are
not a replacement for a broker's live pre-trade validator (which also knows
board, venue, borrow inventory, halts and account permissions).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class MarketRule:
    market: str
    currency: str
    timezone: str
    lot_size: int
    supports_short: bool
    price_tick: float
    daily_price_limit_pct: Optional[float]
    session_note: str

    def validate_quantity(self, quantity: float, side: str) -> list[str]:
        warnings: list[str] = []
        if quantity <= 0:
            return ["quantity must be positive"]
        if abs(quantity / self.lot_size - round(quantity / self.lot_size)) > 1e-9:
            warnings.append(f"{self.market} quantity must be a multiple of lot size {self.lot_size}")
        if side.upper() == "SELL_SHORT" and not self.supports_short:
            warnings.append(f"{self.market} does not permit default stock short selling")
        return warnings

    def is_at_price_limit(self, return_pct: float, direction: str, tolerance: float = 0.001) -> bool:
        """Whether a trade direction is likely blocked by a daily price limit."""
        if self.daily_price_limit_pct is None:
            return False
        limit = self.daily_price_limit_pct
        if direction.upper() in {"BUY", "COVER"}:
            return return_pct >= limit - tolerance
        if direction.upper() in {"SELL", "SELL_SHORT"}:
            return return_pct <= -limit + tolerance
        return False


class CNEquityRules(MarketRule):
    def __init__(self, *, etf: bool = False, board: Optional[str] = None):
        # Main-board A shares and most ETFs use 100-share lots. STAR/ChiNext
        # may use a 20% band; callers can opt in explicitly rather than
        # silently applying the wrong limit to every Chinese instrument.
        board_name = (board or "main").lower()
        limit = 0.20 if board_name in {"star", "chinext", "创业板", "科创板"} else 0.10
        super().__init__(
            market="CN",
            currency="CNY",
            timezone="Asia/Shanghai",
            lot_size=100,
            supports_short=False,
            price_tick=0.01,
            daily_price_limit_pct=limit,
            session_note="T+1 股票；涨跌停、停牌和板块差异需以交易所/券商回报为准",
        )


class USEquityRules(MarketRule):
    def __init__(self):
        super().__init__(
            market="US",
            currency="USD",
            timezone="America/New_York",
            lot_size=1,
            supports_short=True,
            price_tick=0.01,
            daily_price_limit_pct=None,
            session_note="美股通常支持整股交易；做空仍需账户权限与实时借券可用性",
        )


def get_market_rules(market: str, *, instrument_type: str = "STOCK", board: Optional[str] = None) -> MarketRule:
    normalized = market.strip().upper()
    if normalized in {"CN", "A股", "CHINA"}:
        return CNEquityRules(etf=instrument_type.upper() == "ETF", board=board)
    if normalized in {"US", "USA", "美国"}:
        return USEquityRules()
    raise ValueError(f"unsupported market rules: {market}")


def list_market_rules() -> list[dict[str, object]]:
    return [
        _to_dict(CNEquityRules()),
        _to_dict(CNEquityRules(board="star")),
        _to_dict(USEquityRules()),
    ]


def _to_dict(rule: MarketRule) -> dict[str, object]:
    return {
        "market": rule.market,
        "currency": rule.currency,
        "timezone": rule.timezone,
        "lot_size": rule.lot_size,
        "supports_short": rule.supports_short,
        "price_tick": rule.price_tick,
        "daily_price_limit_pct": rule.daily_price_limit_pct,
        "session_note": rule.session_note,
    }
