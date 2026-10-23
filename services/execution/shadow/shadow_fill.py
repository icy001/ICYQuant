"""Shadow fill — a simulated execution record (Commit 016 §7).

Field set per §7, plus the Commit 009 price provenance
(``price_source``: BUY → ASK / SELL → BID / fallback LAST, §8) and the
§9 no-lookahead timestamps::

    signal_timestamp ≤ market_timestamp ≤ execution_timestamp

Fill ids are namespaced ``SHDF-`` (never a broker fill id, §26).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Optional


class ShadowFillStatus(str, Enum):
    FILLED = "FILLED"
    REJECTED = "REJECTED"


def _parse_dt(raw) -> Optional[datetime]:
    if raw in (None, ""):
        return None
    if isinstance(raw, datetime):
        parsed = raw
    else:
        try:
            parsed = datetime.fromisoformat(str(raw))
        except (TypeError, ValueError):
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _parse_decimal(raw) -> Decimal:
    return Decimal(str(raw)) if raw not in (None, "") else Decimal("0")


@dataclass(frozen=True)
class ShadowFill:
    """One simulated fill against real market data (§7)."""

    fill_id: str
    order_id: str
    symbol: str
    side: str
    quantity: int
    price: Decimal
    price_source: str
    market_timestamp: Optional[datetime]
    execution_timestamp: Optional[datetime]
    signal_timestamp: Optional[datetime] = None
    slippage_bps: float = 0.0
    commission: Decimal = Decimal("0")
    status: str = ShadowFillStatus.FILLED.value

    @property
    def notional(self) -> Decimal:
        return self.price * self.quantity

    def as_dict(self) -> dict:
        return {
            "fill_id": self.fill_id,
            "order_id": self.order_id,
            "symbol": self.symbol,
            "side": str(self.side).upper(),
            "quantity": int(self.quantity),
            "price": str(self.price),
            "price_source": self.price_source,
            "notional": str(self.notional),
            "market_timestamp": (
                self.market_timestamp.isoformat()
                if self.market_timestamp
                else None
            ),
            "execution_timestamp": (
                self.execution_timestamp.isoformat()
                if self.execution_timestamp
                else None
            ),
            "signal_timestamp": (
                self.signal_timestamp.isoformat()
                if self.signal_timestamp
                else None
            ),
            "slippage_bps": self.slippage_bps,
            "commission": str(self.commission),
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, payload: dict) -> "ShadowFill":
        return cls(
            fill_id=payload["fill_id"],
            order_id=payload["order_id"],
            symbol=payload["symbol"],
            side=str(payload["side"]).upper(),
            quantity=int(payload["quantity"]),
            price=_parse_decimal(payload.get("price")),
            price_source=payload.get("price_source") or "LAST",
            market_timestamp=_parse_dt(payload.get("market_timestamp")),
            execution_timestamp=_parse_dt(payload.get("execution_timestamp")),
            signal_timestamp=_parse_dt(payload.get("signal_timestamp")),
            slippage_bps=float(payload.get("slippage_bps") or 0.0),
            commission=_parse_decimal(payload.get("commission")),
            status=str(payload.get("status") or "FILLED").upper(),
        )


__all__ = ["ShadowFill", "ShadowFillStatus"]
