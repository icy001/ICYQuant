"""
Position Domain Events

POSITION_INCREASED  — position quantity grew (BUY fill applied).
POSITION_DECREASED  — position quantity shrank (SELL fill applied).
POSITION_CLOSED     — position fully liquidated.
POSITION_REBUILT    — position reconstructed from event replay.

Every position event carries source lineage so we can trace:
    "who created this position change?"
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


# ------------------------------------------------------------------
#  Event type registry
# ------------------------------------------------------------------

class PositionEventType:
    POSITION_INCREASED = "POSITION_INCREASED"
    POSITION_DECREASED = "POSITION_DECREASED"
    POSITION_CLOSED = "POSITION_CLOSED"
    POSITION_REBUILT = "POSITION_REBUILT"


# ------------------------------------------------------------------
#  Base event
# ------------------------------------------------------------------

@dataclass
class PositionEvent:
    """Base class for all Position domain events."""

    event_type: str
    position_id: str
    account_id: str
    instrument_id: str
    side: str

    previous_quantity: float
    delta_quantity: float
    new_quantity: float

    average_price: float
    realized_pnl: float = 0.0

    # ── source tracing ─────────────────────────────────────────
    source_order_id: str = ""
    source_execution_id: str = ""
    source_event_id: str = ""

    # ── lineage ────────────────────────────────────────────────
    correlation_id: str = ""
    causation_id: str = ""
    lineage_id: str = ""

    # ── metadata ───────────────────────────────────────────────
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        """Serialize to dictionary for envelope payload."""
        return {
            "event_type": self.event_type,
            "position_id": self.position_id,
            "account_id": self.account_id,
            "instrument_id": self.instrument_id,
            "side": self.side,
            "previous_quantity": self.previous_quantity,
            "delta_quantity": self.delta_quantity,
            "new_quantity": self.new_quantity,
            "average_price": self.average_price,
            "realized_pnl": self.realized_pnl,
            "source_order_id": self.source_order_id,
            "source_execution_id": self.source_execution_id,
            "source_event_id": self.source_event_id,
            "correlation_id": self.correlation_id,
            "causation_id": self.causation_id,
            "lineage_id": self.lineage_id,
            "timestamp": self.timestamp.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PositionEvent":
        """Deserialize from dictionary."""
        event_type = data.get("event_type", "")

        if event_type == PositionEventType.POSITION_INCREASED:
            return PositionIncreasedEvent(
                position_id=data.get("position_id", ""),
                account_id=data.get("account_id", ""),
                instrument_id=data.get("instrument_id", ""),
                side=data.get("side", ""),
                previous_quantity=data.get("previous_quantity", 0.0),
                delta_quantity=data.get("delta_quantity", 0.0),
                new_quantity=data.get("new_quantity", 0.0),
                average_price=data.get("average_price", 0.0),
                realized_pnl=data.get("realized_pnl", 0.0),
                source_order_id=data.get("source_order_id", ""),
                source_execution_id=data.get("source_execution_id", ""),
                source_event_id=data.get("source_event_id", ""),
                correlation_id=data.get("correlation_id", ""),
                causation_id=data.get("causation_id", ""),
                lineage_id=data.get("lineage_id", ""),
            )
        elif event_type == PositionEventType.POSITION_DECREASED:
            return PositionDecreasedEvent(
                position_id=data.get("position_id", ""),
                account_id=data.get("account_id", ""),
                instrument_id=data.get("instrument_id", ""),
                side=data.get("side", ""),
                previous_quantity=data.get("previous_quantity", 0.0),
                delta_quantity=data.get("delta_quantity", 0.0),
                new_quantity=data.get("new_quantity", 0.0),
                average_price=data.get("average_price", 0.0),
                realized_pnl=data.get("realized_pnl", 0.0),
                source_order_id=data.get("source_order_id", ""),
                source_execution_id=data.get("source_execution_id", ""),
                source_event_id=data.get("source_event_id", ""),
                correlation_id=data.get("correlation_id", ""),
                causation_id=data.get("causation_id", ""),
                lineage_id=data.get("lineage_id", ""),
            )
        elif event_type == PositionEventType.POSITION_CLOSED:
            return PositionClosedEvent(
                position_id=data.get("position_id", ""),
                account_id=data.get("account_id", ""),
                instrument_id=data.get("instrument_id", ""),
                side=data.get("side", ""),
                previous_quantity=data.get("previous_quantity", 0.0),
                delta_quantity=data.get("delta_quantity", 0.0),
                new_quantity=data.get("new_quantity", 0.0),
                average_price=data.get("average_price", 0.0),
                realized_pnl=data.get("realized_pnl", 0.0),
                source_order_id=data.get("source_order_id", ""),
                source_execution_id=data.get("source_execution_id", ""),
                source_event_id=data.get("source_event_id", ""),
                correlation_id=data.get("correlation_id", ""),
                causation_id=data.get("causation_id", ""),
                lineage_id=data.get("lineage_id", ""),
            )
        elif event_type == PositionEventType.POSITION_REBUILT:
            return PositionRebuiltEvent(
                position_id=data.get("position_id", ""),
                account_id=data.get("account_id", ""),
                instrument_id=data.get("instrument_id", ""),
                side=data.get("side", ""),
                previous_quantity=data.get("previous_quantity", 0.0),
                delta_quantity=data.get("delta_quantity", 0.0),
                new_quantity=data.get("new_quantity", 0.0),
                average_price=data.get("average_price", 0.0),
                realized_pnl=data.get("realized_pnl", 0.0),
                source_order_id=data.get("source_order_id", ""),
                source_execution_id=data.get("source_execution_id", ""),
                source_event_id=data.get("source_event_id", ""),
                correlation_id=data.get("correlation_id", ""),
                causation_id=data.get("causation_id", ""),
                lineage_id=data.get("lineage_id", ""),
            )
        else:
            return PositionEvent(
                event_type=event_type,
                position_id=data.get("position_id", ""),
                account_id=data.get("account_id", ""),
                instrument_id=data.get("instrument_id", ""),
                side=data.get("side", ""),
                previous_quantity=data.get("previous_quantity", 0.0),
                delta_quantity=data.get("delta_quantity", 0.0),
                new_quantity=data.get("new_quantity", 0.0),
                average_price=data.get("average_price", 0.0),
                realized_pnl=data.get("realized_pnl", 0.0),
                source_order_id=data.get("source_order_id", ""),
                source_execution_id=data.get("source_execution_id", ""),
                source_event_id=data.get("source_event_id", ""),
                correlation_id=data.get("correlation_id", ""),
                causation_id=data.get("causation_id", ""),
                lineage_id=data.get("lineage_id", ""),
            )


class PositionIncreasedEvent(PositionEvent):
    """Position quantity increased (from a BUY fill)."""

    def __init__(
        self,
        *,
        position_id: str,
        account_id: str,
        instrument_id: str,
        side: str,
        previous_quantity: float,
        delta_quantity: float,
        new_quantity: float,
        average_price: float,
        realized_pnl: float = 0.0,
        source_order_id: str = "",
        source_execution_id: str = "",
        source_event_id: str = "",
        correlation_id: str = "",
        causation_id: str = "",
        lineage_id: str = "",
        timestamp: Optional[datetime] = None,
    ) -> None:
        super().__init__(
            event_type=PositionEventType.POSITION_INCREASED,
            position_id=position_id,
            account_id=account_id,
            instrument_id=instrument_id,
            side=side,
            previous_quantity=previous_quantity,
            delta_quantity=delta_quantity,
            new_quantity=new_quantity,
            average_price=average_price,
            realized_pnl=realized_pnl,
            source_order_id=source_order_id,
            source_execution_id=source_execution_id,
            source_event_id=source_event_id,
            correlation_id=correlation_id,
            causation_id=causation_id,
            lineage_id=lineage_id,
            timestamp=timestamp if timestamp is not None else datetime.now(timezone.utc),
        )


class PositionDecreasedEvent(PositionEvent):
    """Position quantity decreased (from a SELL fill), still open."""

    def __init__(
        self,
        *,
        position_id: str,
        account_id: str,
        instrument_id: str,
        side: str,
        previous_quantity: float,
        delta_quantity: float,
        new_quantity: float,
        average_price: float,
        realized_pnl: float = 0.0,
        source_order_id: str = "",
        source_execution_id: str = "",
        source_event_id: str = "",
        correlation_id: str = "",
        causation_id: str = "",
        lineage_id: str = "",
        timestamp: Optional[datetime] = None,
    ) -> None:
        super().__init__(
            event_type=PositionEventType.POSITION_DECREASED,
            position_id=position_id,
            account_id=account_id,
            instrument_id=instrument_id,
            side=side,
            previous_quantity=previous_quantity,
            delta_quantity=delta_quantity,
            new_quantity=new_quantity,
            average_price=average_price,
            realized_pnl=realized_pnl,
            source_order_id=source_order_id,
            source_execution_id=source_execution_id,
            source_event_id=source_event_id,
            correlation_id=correlation_id,
            causation_id=causation_id,
            lineage_id=lineage_id,
            timestamp=timestamp if timestamp is not None else datetime.now(timezone.utc),
        )


class PositionClosedEvent(PositionEvent):
    """Position fully closed out."""

    def __init__(
        self,
        *,
        position_id: str,
        account_id: str,
        instrument_id: str,
        side: str,
        previous_quantity: float,
        delta_quantity: float,
        new_quantity: float,
        average_price: float,
        realized_pnl: float = 0.0,
        source_order_id: str = "",
        source_execution_id: str = "",
        source_event_id: str = "",
        correlation_id: str = "",
        causation_id: str = "",
        lineage_id: str = "",
        timestamp: Optional[datetime] = None,
    ) -> None:
        super().__init__(
            event_type=PositionEventType.POSITION_CLOSED,
            position_id=position_id,
            account_id=account_id,
            instrument_id=instrument_id,
            side=side,
            previous_quantity=previous_quantity,
            delta_quantity=delta_quantity,
            new_quantity=new_quantity,
            average_price=average_price,
            realized_pnl=realized_pnl,
            source_order_id=source_order_id,
            source_execution_id=source_execution_id,
            source_event_id=source_event_id,
            correlation_id=correlation_id,
            causation_id=causation_id,
            lineage_id=lineage_id,
            timestamp=timestamp if timestamp is not None else datetime.now(timezone.utc),
        )


class PositionRebuiltEvent(PositionEvent):
    """Position reconstructed from event replay or recovery."""

    def __init__(
        self,
        *,
        position_id: str,
        account_id: str,
        instrument_id: str,
        side: str,
        previous_quantity: float,
        delta_quantity: float,
        new_quantity: float,
        average_price: float,
        realized_pnl: float = 0.0,
        source_order_id: str = "",
        source_execution_id: str = "",
        source_event_id: str = "",
        correlation_id: str = "",
        causation_id: str = "",
        lineage_id: str = "",
        timestamp: Optional[datetime] = None,
    ) -> None:
        super().__init__(
            event_type=PositionEventType.POSITION_REBUILT,
            position_id=position_id,
            account_id=account_id,
            instrument_id=instrument_id,
            side=side,
            previous_quantity=previous_quantity,
            delta_quantity=delta_quantity,
            new_quantity=new_quantity,
            average_price=average_price,
            realized_pnl=realized_pnl,
            source_order_id=source_order_id,
            source_execution_id=source_execution_id,
            source_event_id=source_event_id,
            correlation_id=correlation_id,
            causation_id=causation_id,
            lineage_id=lineage_id,
            timestamp=timestamp if timestamp is not None else datetime.now(timezone.utc),
        )
