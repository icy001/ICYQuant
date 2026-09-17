"""Shadow order + order intent (Commit 016 §5 / §6).

An :class:`OrderIntent` is what the decision chain hands to Shadow
execution — never a raw strategy signal (§6)::

    Strategy Signal → Risk Decision → Order Intent → Shadow Execution

A :class:`ShadowOrder` is what Shadow execution produces.  Its id is
namespaced ``SHD-`` so a shadow order can never be mistaken for a
broker order id (§26 safety matrix).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Optional
from uuid import uuid4


class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    """Commit 016 simulates MARKET orders only (§5)."""

    MARKET = "MARKET"


class ShadowOrderStatus(str, Enum):
    ACCEPTED = "ACCEPTED"
    FILLED = "FILLED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


def new_intent_id() -> str:
    return f"SHIN-{uuid4().hex[:12].upper()}"


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


def _parse_decimal(raw) -> Optional[Decimal]:
    if raw in (None, ""):
        return None
    try:
        return Decimal(str(raw))
    except ArithmeticError:
        return None


@dataclass(frozen=True)
class OrderIntent:
    """The §6 intent record — plain facts, no execution decisions."""

    intent_id: str
    symbol: str
    side: str
    quantity: int
    order_type: str = OrderType.MARKET.value
    strategy_id: str = ""
    timestamp: Optional[datetime] = None

    def __post_init__(self) -> None:
        if not self.intent_id:
            raise ValueError("intent_id must not be empty")
        if not self.symbol:
            raise ValueError("symbol must not be empty")

    def as_dict(self) -> dict:
        return {
            "intent_id": self.intent_id,
            "symbol": self.symbol,
            "side": str(self.side).upper(),
            "quantity": int(self.quantity),
            "order_type": str(self.order_type).upper(),
            "strategy_id": self.strategy_id,
            "timestamp": (
                self.timestamp.isoformat() if self.timestamp else None
            ),
        }

    @classmethod
    def from_dict(cls, payload: dict) -> "OrderIntent":
        return cls(
            intent_id=payload.get("intent_id") or new_intent_id(),
            symbol=payload["symbol"],
            side=str(payload["side"]).upper(),
            quantity=int(payload["quantity"]),
            order_type=str(payload.get("order_type") or "MARKET").upper(),
            strategy_id=payload.get("strategy_id") or "",
            timestamp=_parse_dt(payload.get("timestamp")),
        )


@dataclass(frozen=True)
class ShadowOrder:
    """A shadow order — simulated execution, never a broker order."""

    order_id: str
    intent_id: str
    symbol: str
    side: str
    quantity: int
    order_type: str
    strategy_id: str
    status: str
    reason: Optional[str] = None
    created_at: Optional[datetime] = None
    signal_timestamp: Optional[datetime] = None
    filled_quantity: int = 0
    avg_fill_price: Optional[Decimal] = None

    @property
    def is_terminal(self) -> bool:
        return self.status in (
            ShadowOrderStatus.FILLED.value,
            ShadowOrderStatus.REJECTED.value,
            ShadowOrderStatus.CANCELLED.value,
        )

    def as_dict(self) -> dict:
        return {
            "order_id": self.order_id,
            "intent_id": self.intent_id,
            "symbol": self.symbol,
            "side": str(self.side).upper(),
            "quantity": int(self.quantity),
            "order_type": str(self.order_type).upper(),
            "strategy_id": self.strategy_id,
            "status": self.status,
            "reason": self.reason,
            "created_at": (
                self.created_at.isoformat() if self.created_at else None
            ),
            "signal_timestamp": (
                self.signal_timestamp.isoformat()
                if self.signal_timestamp
                else None
            ),
            "filled_quantity": int(self.filled_quantity),
            "avg_fill_price": (
                str(self.avg_fill_price)
                if self.avg_fill_price is not None
                else None
            ),
        }

    @classmethod
    def from_dict(cls, payload: dict) -> "ShadowOrder":
        return cls(
            order_id=payload["order_id"],
            intent_id=payload.get("intent_id") or "",
            symbol=payload["symbol"],
            side=str(payload["side"]).upper(),
            quantity=int(payload["quantity"]),
            order_type=str(payload.get("order_type") or "MARKET").upper(),
            strategy_id=payload.get("strategy_id") or "",
            status=str(payload.get("status") or "ACCEPTED").upper(),
            reason=payload.get("reason"),
            created_at=_parse_dt(payload.get("created_at")),
            signal_timestamp=_parse_dt(payload.get("signal_timestamp")),
            filled_quantity=int(payload.get("filled_quantity") or 0),
            avg_fill_price=_parse_decimal(payload.get("avg_fill_price")),
        )


__all__ = [
    "OrderSide",
    "OrderType",
    "ShadowOrderStatus",
    "OrderIntent",
    "ShadowOrder",
    "new_intent_id",
]
