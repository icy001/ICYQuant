"""Lifecycle Dispatcher — Event creation and routing.

Coordinates event creation, dispatching to the transition engine,
and managing the event pipeline. Acts as the intermediary between
external triggers (broker ACK, fills, etc.) and the transition engine.

Pipeline:
    External Event → LifecycleDispatcher → TransitionEngine → EventStore
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from services.oms.lifecycle.state_transition_validator import LifecycleStatus
from services.oms.lifecycle.transition_engine import TransitionEngine

logger = logging.getLogger(__name__)


class LifecycleEventType(str, Enum):
    """Types of lifecycle events routed through the dispatcher."""
    VALIDATE = "validate"
    ROUTE = "route"
    DISPATCH = "dispatch"
    ACKNOWLEDGE = "acknowledge"
    PENDING = "pending"
    WORKING = "working"
    PARTIAL_FILL = "partial_fill"
    FILL = "fill"
    REPLACE = "replace"
    CANCEL = "cancel"
    REJECT = "reject"
    EXPIRE = "expire"
    SUSPEND = "suspend"
    RESUME = "resume"
    RECOVER = "recover"


@dataclass
class LifecycleEvent:
    """An event to be dispatched through the lifecycle pipeline."""
    event_id: str
    order_id: str
    event_type: LifecycleEventType
    from_status: LifecycleStatus
    to_status: LifecycleStatus
    sequence_id: int = 0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    payload: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "event_id": self.event_id,
            "order_id": self.order_id,
            "event_type": self.event_type.value,
            "from_status": self.from_status.value,
            "to_status": self.to_status.value,
            "sequence_id": self.sequence_id,
            "timestamp": self.timestamp.isoformat(),
            "payload": self.payload,
            "metadata": self.metadata,
        }


class LifecycleDispatcher:
    """Dispatches lifecycle events to the transition engine.

    Creates properly-formatted events, maps external triggers to
    valid state transitions, and manages the event pipeline from
    receipt through transition execution.

    Usage::

        dispatcher = LifecycleDispatcher(transition_engine)
        event = dispatcher.create_event(
            order_id="...",
            event_type=LifecycleEventType.FILL,
            from_status=LifecycleStatus.WORKING,
        )
        result = await dispatcher.dispatch(order, event)
    """

    def __init__(self, transition_engine: TransitionEngine) -> None:
        """Initialize lifecycle dispatcher.

        Args:
            transition_engine: Transition engine for executing transitions
        """
        self._transition_engine = transition_engine
        self._sequence_counter: int = 0

    def create_event(
        self,
        order_id: str,
        event_type: LifecycleEventType,
        from_status: LifecycleStatus,
        payload: Optional[dict[str, Any]] = None,
        metadata: Optional[dict[str, Any]] = None,
        event_id: Optional[str] = None,
    ) -> LifecycleEvent:
        """Create a new lifecycle event.

        Args:
            order_id: Order identifier
            event_type: Type of event
            from_status: Current order status
            payload: Event-specific data
            metadata: Additional context
            event_id: Optional custom event ID

        Returns:
            A new LifecycleEvent ready for dispatch
        """
        self._sequence_counter += 1

        to_status = self._resolve_target_status(event_type, from_status)

        return LifecycleEvent(
            event_id=event_id or str(uuid.uuid4()),
            order_id=order_id,
            event_type=event_type,
            from_status=from_status,
            to_status=to_status,
            sequence_id=self._sequence_counter,
            payload=payload or {},
            metadata=metadata or {},
        )

    def _resolve_target_status(
        self,
        event_type: LifecycleEventType,
        from_status: LifecycleStatus,
    ) -> LifecycleStatus:
        """Determine the target status for a given event type.

        Args:
            event_type: Type of lifecycle event
            from_status: Current order status

        Returns:
            The resolved target lifecycle status
        """
        # Event-to-status mapping
        mapping = {
            LifecycleEventType.VALIDATE: LifecycleStatus.VALIDATED,
            LifecycleEventType.ROUTE: LifecycleStatus.ROUTED,
            LifecycleEventType.DISPATCH: LifecycleStatus.SUBMITTED,
            LifecycleEventType.ACKNOWLEDGE: LifecycleStatus.ACKNOWLEDGED,
            LifecycleEventType.PENDING: LifecycleStatus.SUBMITTED,
            LifecycleEventType.WORKING: LifecycleStatus.WORKING,
            LifecycleEventType.PARTIAL_FILL: LifecycleStatus.PARTIALLY_FILLED,
            LifecycleEventType.FILL: LifecycleStatus.FILLED,
            LifecycleEventType.REPLACE: LifecycleStatus.REPLACED,
            LifecycleEventType.CANCEL: LifecycleStatus.CANCELLED,
            LifecycleEventType.REJECT: LifecycleStatus.REJECTED,
            LifecycleEventType.EXPIRE: LifecycleStatus.EXPIRED,
            LifecycleEventType.SUSPEND: LifecycleStatus.SUSPENDED,
            LifecycleEventType.RESUME: LifecycleStatus.WORKING,
            LifecycleEventType.RECOVER: LifecycleStatus.WORKING,
        }
        return mapping.get(event_type, from_status)

    async def get_next_event_id(self) -> str:
        """Generate a unique event ID."""
        return str(uuid.uuid4())

    @property
    def sequence_counter(self) -> int:
        """Current sequence counter value."""
        return self._sequence_counter

    def to_dict(self) -> dict[str, Any]:
        """Serialize dispatcher state."""
        return {
            "sequence_counter": self._sequence_counter,
            "transition_engine": self._transition_engine.to_dict(),
        }
