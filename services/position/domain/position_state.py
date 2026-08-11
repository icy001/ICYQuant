"""
Position State / Projection

The PositionState is a query-side projection that is rebuilt
by replaying Position domain events.

It is NOT the aggregate — it is a read model.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from .position_event import (
    PositionClosedEvent,
    PositionDecreasedEvent,
    PositionEvent,
    PositionEventType,
    PositionIncreasedEvent,
)


@dataclass
class PositionState:
    """
    Read-side projection of a single position.

    Rebuildable from the position event stream.
    """

    position_id: str
    account_id: str
    instrument_id: str
    side: str  # "LONG" / "SHORT"

    quantity: float = 0.0
    average_price: float = 0.0

    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0

    status: str = "OPEN"  # OPEN / CLOSED
    version: int = 0

    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # ── source lineage ─────────────────────────────────────────
    last_event_id: str = ""
    last_order_id: str = ""
    last_execution_id: str = ""

    @classmethod
    def empty(
        cls,
        position_id: str,
        account_id: str,
        instrument_id: str,
        side: str = "LONG",
    ) -> PositionState:
        """Create an empty / zero-quantity position projection."""
        return cls(
            position_id=position_id,
            account_id=account_id,
            instrument_id=instrument_id,
            side=side,
        )

    # ------------------------------------------------------------------
    #  Apply events (projection rebuild)
    # ------------------------------------------------------------------

    def apply_event(self, event: PositionEvent) -> None:
        """Apply a single position event to update projection state."""
        self.position_id = event.position_id
        self.account_id = event.account_id
        self.instrument_id = event.instrument_id
        self.side = event.side
        self.quantity = event.new_quantity
        self.average_price = event.average_price
        self.realized_pnl = event.realized_pnl
        self.version += 1
        self.updated_at = event.timestamp
        self.last_event_id = event.source_event_id
        self.last_order_id = event.source_order_id
        self.last_execution_id = event.source_execution_id

        if event.event_type == PositionEventType.POSITION_CLOSED:
            self.status = "CLOSED"

    @classmethod
    def from_events(cls, events: list[PositionEvent]) -> PositionState:
        """Rebuild projection from a sequence of position events."""
        if not events:
            raise ValueError("Cannot build PositionState from empty event list")

        state = cls.empty(
            position_id=events[0].position_id,
            account_id=events[0].account_id,
            instrument_id=events[0].instrument_id,
            side=events[0].side,
        )
        for event in events:
            state.apply_event(event)
        return state

    # ------------------------------------------------------------------
    #  Properties
    # ------------------------------------------------------------------

    @property
    def is_open(self) -> bool:
        return self.status == "OPEN" and self.quantity > 0

    @property
    def is_closed(self) -> bool:
        return self.status == "CLOSED" or self.quantity <= 0

    @property
    def exposure(self) -> float:
        return self.quantity * self.average_price

    @property
    def key(self) -> tuple[str, str, str]:
        return (self.account_id, self.instrument_id, self.side)

    def to_dict(self) -> dict:
        return {
            "position_id": self.position_id,
            "account_id": self.account_id,
            "instrument_id": self.instrument_id,
            "side": self.side,
            "quantity": self.quantity,
            "average_price": self.average_price,
            "realized_pnl": self.realized_pnl,
            "unrealized_pnl": self.unrealized_pnl,
            "status": self.status,
            "version": self.version,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "last_event_id": self.last_event_id,
            "last_order_id": self.last_order_id,
            "last_execution_id": self.last_execution_id,
        }
