"""
Position Aggregate

Position is the source of truth for current holdings.
It applies execution facts and emits domain events.

Key rules:
- Position does NOT read OMS database directly.
- Position does NOT manage cash / fees / ledger entries.
- Position only tracks: quantity, average_price, exposure, lifecycle.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional, Tuple

from .position_event import (
    PositionClosedEvent,
    PositionDecreasedEvent,
    PositionEvent,
    PositionIncreasedEvent,
)


class PositionSide(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"
    FLAT = "FLAT"


class PositionStatus(str, Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"


@dataclass
class Position:
    """
    Position aggregate root.

    Key: (account_id, instrument_id, side)

    Each execution application increments version for optimistic concurrency.
    """

    position_id: str
    account_id: str
    instrument_id: str
    side: PositionSide

    quantity: float = 0.0
    average_price: float = 0.0

    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0

    version: int = 1
    status: PositionStatus = PositionStatus.OPEN

    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # ── lineage / source tracking ──────────────────────────────
    last_event_id: str = ""
    last_order_id: str = ""
    last_execution_id: str = ""

    # ── uncommitted events ─────────────────────────────────────
    _pending_events: List[PositionEvent] = field(default_factory=list, repr=False)

    # ------------------------------------------------------------------
    #  Factory
    # ------------------------------------------------------------------

    @classmethod
    def open_long(
        cls,
        position_id: str,
        account_id: str,
        instrument_id: str,
        quantity: float = 0.0,
        average_price: float = 0.0,
    ) -> "Position":

        return cls(
            position_id=position_id,
            account_id=account_id,
            instrument_id=instrument_id,
            side=PositionSide.LONG,
            quantity=quantity,
            average_price=average_price,
        )

    @classmethod
    def open_short(
        cls,
        position_id: str,
        account_id: str,
        instrument_id: str,
        quantity: float = 0.0,
        average_price: float = 0.0,
    ) -> "Position":

        return cls(
            position_id=position_id,
            account_id=account_id,
            instrument_id=instrument_id,
            side=PositionSide.SHORT,
            quantity=quantity,
            average_price=average_price,
        )

    # ------------------------------------------------------------------
    #  Properties
    # ------------------------------------------------------------------

    @property
    def is_open(self) -> bool:
        return self.status == PositionStatus.OPEN and self.quantity > 0

    @property
    def is_closed(self) -> bool:
        return self.status == PositionStatus.CLOSED or self.quantity <= 0

    @property
    def exposure(self) -> float:
        """Gross exposure = quantity * average_price."""
        return self.quantity * self.average_price

    @property
    def signed_quantity(self) -> float:
        """LONG → positive, SHORT → negative."""
        return self.quantity if self.side == PositionSide.LONG else -self.quantity

    @property
    def key(self) -> Tuple[str, str, PositionSide]:
        """Unique position key: (account_id, instrument_id, side)."""
        return (self.account_id, self.instrument_id, self.side)

    # ------------------------------------------------------------------
    #  Core business logic — apply execution
    # ------------------------------------------------------------------

    def apply_fill(
        self,
        *,
        fill_quantity: float,
        fill_price: float,
        execution_id: str,
        order_id: str,
        source_event_id: str,
        correlation_id: str = "",
        causation_id: str = "",
        lineage_id: str = "",
    ) -> Optional[PositionEvent]:
        """
        Apply a confirmed fill to this position.

        Returns the generated PositionEvent or None if no-op.

        Raises:
            PositionOverFillError if fill exceeds expected bounds.
        """
        if fill_quantity <= 0:
            return None
        if fill_price <= 0:
            raise ValueError("fill_price must be > 0")

        old_quantity = self.quantity
        old_avg = self.average_price

        # Update quantity
        self.quantity += fill_quantity

        # Recalculate weighted average price (BUY side or increasing LONG)
        if self.side == PositionSide.LONG:
            if old_quantity > 0:
                total_cost = old_quantity * old_avg + fill_quantity * fill_price
                self.average_price = total_cost / self.quantity
            else:
                self.average_price = fill_price

        self.version += 1
        self.updated_at = datetime.now(timezone.utc)
        self.last_event_id = source_event_id
        self.last_order_id = order_id
        self.last_execution_id = execution_id

        # Determine event type
        if old_quantity == 0:
            event = PositionIncreasedEvent(
                position_id=self.position_id,
                account_id=self.account_id,
                instrument_id=self.instrument_id,
                side=self.side.value,
                previous_quantity=old_quantity,
                delta_quantity=fill_quantity,
                new_quantity=self.quantity,
                average_price=self.average_price,
                source_order_id=order_id,
                source_execution_id=execution_id,
                source_event_id=source_event_id,
                correlation_id=correlation_id,
                causation_id=causation_id,
                lineage_id=lineage_id,
            )
        else:
            event = PositionIncreasedEvent(
                position_id=self.position_id,
                account_id=self.account_id,
                instrument_id=self.instrument_id,
                side=self.side.value,
                previous_quantity=old_quantity,
                delta_quantity=fill_quantity,
                new_quantity=self.quantity,
                average_price=self.average_price,
                source_order_id=order_id,
                source_execution_id=execution_id,
                source_event_id=source_event_id,
                correlation_id=correlation_id,
                causation_id=causation_id,
                lineage_id=lineage_id,
            )

        self._pending_events.append(event)
        return event

    def apply_reduction(
        self,
        *,
        reduction_quantity: float,
        fill_price: float,
        execution_id: str,
        order_id: str,
        source_event_id: str,
        correlation_id: str = "",
        causation_id: str = "",
        lineage_id: str = "",
    ) -> Optional[PositionEvent]:
        """
        Apply a SELL reduction (LONG position) or BUY reduction (SHORT position).

        Returns the generated PositionEvent or None if no-op.
        """
        if reduction_quantity <= 0:
            return None
        if reduction_quantity > self.quantity:
            raise PositionOverFillError(
                f"Cannot reduce {reduction_quantity} when position is only {self.quantity}"
            )

        old_quantity = self.quantity
        realized = reduction_quantity * (fill_price - self.average_price)
        if self.side == PositionSide.SHORT:
            realized = -realized

        self.quantity -= reduction_quantity
        self.realized_pnl += realized

        # Average price unchanged on reduction
        if self.quantity <= 0:
            self.average_price = 0.0

        self.version += 1
        self.updated_at = datetime.now(timezone.utc)
        self.last_event_id = source_event_id
        self.last_order_id = order_id
        self.last_execution_id = execution_id

        if self.quantity <= 0:
            self.status = PositionStatus.CLOSED
            event: PositionEvent = PositionClosedEvent(
                position_id=self.position_id,
                account_id=self.account_id,
                instrument_id=self.instrument_id,
                side=self.side.value,
                previous_quantity=old_quantity,
                delta_quantity=-reduction_quantity,
                new_quantity=0.0,
                average_price=self.average_price,
                realized_pnl=self.realized_pnl,
                source_order_id=order_id,
                source_execution_id=execution_id,
                source_event_id=source_event_id,
                correlation_id=correlation_id,
                causation_id=causation_id,
                lineage_id=lineage_id,
            )
        else:
            event = PositionDecreasedEvent(
                position_id=self.position_id,
                account_id=self.account_id,
                instrument_id=self.instrument_id,
                side=self.side.value,
                previous_quantity=old_quantity,
                delta_quantity=-reduction_quantity,
                new_quantity=self.quantity,
                average_price=self.average_price,
                realized_pnl=self.realized_pnl,
                source_order_id=order_id,
                source_execution_id=execution_id,
                source_event_id=source_event_id,
                correlation_id=correlation_id,
                causation_id=causation_id,
                lineage_id=lineage_id,
            )

        self._pending_events.append(event)
        return event

    def detect_reversal(
        self,
        *,
        reduction_quantity: float,
        order_id: str,
    ) -> bool:
        """
        Detect if the requested reduction would reverse the position.

        Returns True if reduction_quantity > current quantity (meaning
        a full reversal / flip would be needed).
        """
        return reduction_quantity > self.quantity

    # ------------------------------------------------------------------
    #  Snapshot
    # ------------------------------------------------------------------

    def snapshot(self) -> "PositionSnapshot":
        return PositionSnapshot(
            position_id=self.position_id,
            account_id=self.account_id,
            instrument_id=self.instrument_id,
            side=self.side,
            quantity=self.quantity,
            average_price=self.average_price,
            realized_pnl=self.realized_pnl,
            unrealized_pnl=self.unrealized_pnl,
            version=self.version,
            status=self.status,
            updated_at=self.updated_at,
            last_order_id=self.last_order_id,
            last_execution_id=self.last_execution_id,
        )

    def collect_events(self) -> List[PositionEvent]:
        """Drain and return pending domain events."""
        events = self._pending_events[:]
        self._pending_events.clear()
        return events


# ------------------------------------------------------------------
#  Snapshot / Projection
# ------------------------------------------------------------------

@dataclass
class PositionSnapshot:
    """Immutable snapshot of position state at a point in time."""

    position_id: str
    account_id: str
    instrument_id: str
    side: PositionSide

    quantity: float
    average_price: float

    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0

    version: int = 1
    status: PositionStatus = PositionStatus.OPEN

    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    last_order_id: str = ""
    last_execution_id: str = ""

    @property
    def exposure(self) -> float:
        return self.quantity * self.average_price

    def to_dict(self) -> dict:
        return {
            "position_id": self.position_id,
            "account_id": self.account_id,
            "instrument_id": self.instrument_id,
            "side": self.side.value,
            "quantity": self.quantity,
            "average_price": self.average_price,
            "realized_pnl": self.realized_pnl,
            "unrealized_pnl": self.unrealized_pnl,
            "version": self.version,
            "status": self.status.value,
            "updated_at": self.updated_at.isoformat(),
            "last_order_id": self.last_order_id,
            "last_execution_id": self.last_execution_id,
        }


# ------------------------------------------------------------------
#  Domain exceptions
# ------------------------------------------------------------------

class PositionOverFillError(Exception):
    """Fill exceeds expected position bounds."""

    def __init__(self, message: str):
        super().__init__(message)
