"""Execution Event — Event definitions for the EMS event-driven architecture.

All execution operations are driven by events. This module defines the
event types and the base event structure for the Execution Management System.

Event Types:
    EXECUTION_SUBMITTED: Parent order submitted for execution
    EXECUTION_STARTED: Execution engine started processing
    EXECUTION_PAUSED: Execution temporarily paused
    EXECUTION_RESUMED: Execution resumed after pause
    EXECUTION_COMPLETED: All child orders filled
    EXECUTION_CANCELLED: Execution cancelled
    EXECUTION_REJECTED: Execution rejected
    EXECUTION_ERROR: System error
    CHILD_ORDER_CREATED: Algorithm produced a new child order
    CHILD_ORDER_SUBMITTED: Child order sent to broker
    CHILD_ORDER_FILLED: Child order fully filled
    CHILD_ORDER_PARTIAL: Child order partially filled
    CHILD_ORDER_CANCELLED: Child order cancelled
    CHILD_ORDER_REJECTED: Child order rejected
    ALGORITHM_SWITCHED: Execution algorithm changed
    SCHEDULE_TICK: Periodic scheduling pulse
    EXECUTION_SNAPSHOT: State snapshot created

Usage::

    event = ExecutionEvent(
        event_type=ExecutionEventType.EXECUTION_STARTED,
        parent_order_id="PO_001",
        payload={"strategy": "TWAP", "total_qty": 10000},
    )
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


class ExecutionEventType(str, Enum):
    """Execution event type enumeration."""

    # Parent-level events
    EXECUTION_SUBMITTED = "EXECUTION_SUBMITTED"
    EXECUTION_STARTED = "EXECUTION_STARTED"
    EXECUTION_PAUSED = "EXECUTION_PAUSED"
    EXECUTION_RESUMED = "EXECUTION_RESUMED"
    EXECUTION_COMPLETED = "EXECUTION_COMPLETED"
    EXECUTION_CANCELLED = "EXECUTION_CANCELLED"
    EXECUTION_REJECTED = "EXECUTION_REJECTED"
    EXECUTION_ERROR = "EXECUTION_ERROR"

    # Child-level events
    CHILD_ORDER_CREATED = "CHILD_ORDER_CREATED"
    CHILD_ORDER_SUBMITTED = "CHILD_ORDER_SUBMITTED"
    CHILD_ORDER_FILLED = "CHILD_ORDER_FILLED"
    CHILD_ORDER_PARTIAL = "CHILD_ORDER_PARTIAL"
    CHILD_ORDER_CANCELLED = "CHILD_ORDER_CANCELLED"
    CHILD_ORDER_REJECTED = "CHILD_ORDER_REJECTED"

    # Algorithm events
    ALGORITHM_SWITCHED = "ALGORITHM_SWITCHED"
    SCHEDULE_TICK = "SCHEDULE_TICK"

    # System events
    EXECUTION_SNAPSHOT = "EXECUTION_SNAPSHOT"

    @property
    def is_parent_event(self) -> bool:
        """Whether this event type is parent-level."""
        return self.value.startswith("EXECUTION_") and not self.value.startswith("EXECUTION_S")

    @property
    def is_child_event(self) -> bool:
        """Whether this event type is child-order-level."""
        return self.value.startswith("CHILD_ORDER_")

    @property
    def is_algorithm_event(self) -> bool:
        """Whether this event type is algorithm-level."""
        return self in (
            ExecutionEventType.ALGORITHM_SWITCHED,
            ExecutionEventType.SCHEDULE_TICK,
        )


@dataclass
class ExecutionEvent:
    """An execution event representing a state change or operation.

    Attributes:
        event_id: Unique event identifier
        event_type: Type of execution event
        parent_order_id: Associated parent order ID
        child_order_id: Associated child order ID (for child events)
        strategy_id: Associated strategy/algorithm name
        timestamp: Event creation time
        payload: Event-specific data
        sequence: Monotonically increasing sequence number
    """

    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_type: ExecutionEventType = ExecutionEventType.EXECUTION_SUBMITTED
    parent_order_id: str = ""
    child_order_id: Optional[str] = None
    strategy_id: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    payload: dict[str, Any] = field(default_factory=dict)
    sequence: int = 0

    @property
    def is_terminal(self) -> bool:
        """Whether this event represents a terminal state."""
        return self.event_type in (
            ExecutionEventType.EXECUTION_COMPLETED,
            ExecutionEventType.EXECUTION_CANCELLED,
            ExecutionEventType.EXECUTION_REJECTED,
            ExecutionEventType.EXECUTION_ERROR,
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize event to dictionary."""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "parent_order_id": self.parent_order_id,
            "child_order_id": self.child_order_id,
            "strategy_id": self.strategy_id,
            "timestamp": self.timestamp.isoformat(),
            "payload": self.payload,
            "sequence": self.sequence,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ExecutionEvent":
        """Deserialize event from dictionary."""
        return cls(
            event_id=data.get("event_id", str(uuid.uuid4())),
            event_type=ExecutionEventType(data.get("event_type", "EXECUTION_SUBMITTED")),
            parent_order_id=data.get("parent_order_id", ""),
            child_order_id=data.get("child_order_id"),
            strategy_id=data.get("strategy_id", ""),
            payload=data.get("payload", {}),
            sequence=data.get("sequence", 0),
        )
