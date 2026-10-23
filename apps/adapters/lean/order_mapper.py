"""LEAN order / fill events → ICYQuant domain values.

Two directions live here:

* **status normalisation** — LEAN spells the cancelled state ``CANCELED``
  (one L); ICYQuant's own vocabulary uses ``CANCELLED``.  Anything
  unrecognised maps to ``UNKNOWN`` rather than being guessed at.
* **fill → ledger trade** — a filled order event becomes a value shaped
  for :meth:`services.ledger.posting.PostingEngine.post_trade`.

Known limitation of ``PostingEngine`` (pre-existing, not introduced
here): it posts one debit-to-position / credit-to-cash pair and takes
``abs()`` of the amount, so it does not represent a *sell* as a
direction — the sign is carried by the reconciliation layer in the
P0-01 E2E suite, not by the journal entry.  Turning the ledger
double-entry model direction-aware is P0-02 work.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

__all__ = [
    "LEAN_ORDER_STATUS_MAP",
    "LedgerTrade",
    "map_lean_order_status",
    "map_order_event",
    "order_event_to_ledger_trade",
]

LEAN_ORDER_STATUS_MAP = {
    "NEW": "NEW",
    "SUBMITTED": "SUBMITTED",
    "PARTIALLY_FILLED": "PARTIALLY_FILLED",
    "FILLED": "FILLED",
    "CANCELED": "CANCELLED",
    "CANCELLED": "CANCELLED",
    "INVALID": "REJECTED",
}

#: Statuses that carry a real fill quantity.
FILL_STATUSES = frozenset({"FILLED", "PARTIALLY_FILLED"})


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def map_lean_order_status(status: str) -> str:
    """Normalise a LEAN order status into ICYQuant vocabulary.

    Handles both the plain form (``"Filled"``) and the qualified form
    pythonnet can produce (``"OrderStatus.FILLED"``).
    """
    token = str(status).strip().upper().rsplit(".", 1)[-1]

    return LEAN_ORDER_STATUS_MAP.get(token, "UNKNOWN")


def map_order_event(event: dict[str, Any]) -> dict[str, Any]:
    """Normalise a LEAN order event (or the debug line parsed from it)."""
    return {
        "order_id": str(event.get("order_id", "")),
        "signal_id": str(event.get("signal_id", "") or ""),
        "symbol": event.get("symbol"),
        "status": map_lean_order_status(str(event.get("status", "UNKNOWN"))),
        "quantity": event.get("quantity", 0),
        "filled_quantity": event.get("filled_quantity", 0),
        "fill_price": event.get("fill_price"),
        "message": event.get("message"),
        "timestamp": event.get("timestamp"),
    }


@dataclass(frozen=True)
class LedgerTrade:
    """The shape ``PostingEngine.post_trade()`` consumes.

    ``quantity`` is deliberately positive: see the module docstring on
    why direction is a reconciliation concern for now.
    """

    symbol: str
    quantity: Decimal
    price: Decimal
    commission: Decimal = Decimal("0")
    order_id: str = ""
    signal_id: str = ""
    filled_at: str = field(default_factory=_utc_now)


def order_event_to_ledger_trade(
    event: dict[str, Any],
    *,
    commission: Decimal | float | str = Decimal("0"),
) -> LedgerTrade:
    """Convert a normalised, *filled* order event into a ledger trade.

    Raises ``ValueError`` when the event carries no fill — an unfilled
    order must never produce a journal entry.
    """
    normalised = map_order_event(event)

    if normalised["status"] not in FILL_STATUSES:
        raise ValueError(
            f"order event without a fill cannot be posted: "
            f"{normalised['status']}"
        )

    if not normalised["symbol"]:
        raise ValueError("order event without a symbol cannot be posted")

    filled_quantity = Decimal(str(normalised["filled_quantity"] or 0))

    if filled_quantity == 0:
        raise ValueError("order event reports a zero fill")

    fill_price = normalised["fill_price"]

    if fill_price is None:
        raise ValueError("order event without a fill price cannot be posted")

    timestamp = normalised["timestamp"]

    return LedgerTrade(
        symbol=str(normalised["symbol"]),
        quantity=abs(filled_quantity),
        price=Decimal(str(fill_price)),
        commission=Decimal(str(commission)),
        order_id=normalised["order_id"],
        filled_at=str(timestamp) if timestamp else _utc_now(),
    )
