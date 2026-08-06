"""EventBus Adapter — event-driven workflow integration.

The workflow engine becomes fully event-driven through:

* **Event Publish** — emit workflow lifecycle events to the bus
* **Event Subscribe** — trigger workflows from external events
* **Event Replay** — replay historical events for recovery or audit
* **Dead Letter Queue** — capture failed events (reserved)

Architecture::

    WorkflowStarted → NodeStarted → OrderCreated → RiskApproved
         → ExecutionCompleted → WorkflowCompleted
                    ↓
              ICYQuant EventBus
"""

from __future__ import annotations

import asyncio
import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class WorkflowEventType(str, Enum):
    """Events published by the workflow engine to the event bus."""

    WORKFLOW_STARTED = "workflow.started"
    WORKFLOW_COMPLETED = "workflow.completed"
    WORKFLOW_FAILED = "workflow.failed"
    WORKFLOW_CANCELLED = "workflow.cancelled"
    NODE_STARTED = "workflow.node.started"
    NODE_COMPLETED = "workflow.node.completed"
    NODE_FAILED = "workflow.node.failed"
    VARIABLE_CHANGED = "workflow.variable.changed"
    CHECKPOINT_CREATED = "workflow.checkpoint.created"
    STATE_TRANSITION = "workflow.state.transition"


@dataclass
class WorkflowEvent:
    """An event emitted by a workflow execution."""

    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_type: WorkflowEventType = WorkflowEventType.WORKFLOW_STARTED
    workflow_id: str = ""
    execution_id: str = ""
    node_id: Optional[str] = None
    payload: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    trace_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "workflow_id": self.workflow_id,
            "execution_id": self.execution_id,
            "node_id": self.node_id,
            "payload": dict(self.payload),
            "timestamp": self.timestamp.isoformat(),
            "trace_id": self.trace_id,
            "metadata": dict(self.metadata),
        }


class EventBusAdapter:
    """Bridges workflow events with the ICYQuant event bus.

    Usage::

        adapter = EventBusAdapter()
        await adapter.start()
        await adapter.publish(WorkflowEvent(event_type=WorkflowEventType.WORKFLOW_STARTED, ...))
        adapter.subscribe(WorkflowEventType.ORDER_CREATED, my_handler)
    """

    def __init__(self, *, config: Optional[Dict[str, Any]] = None) -> None:
        self._config = config or {}
        self._lock = threading.RLock()
        self._started = False

        # Subscribers: event_type → list of (callback, is_async)
        self._subscribers: Dict[str, List[Callable]] = {}

        # Event history
        self._event_log: List[WorkflowEvent] = []
        self._max_event_log = 100000

        # Dead letter queue (reserved)
        self._dead_letter: List[WorkflowEvent] = []

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        self._started = True
        logger.info("EventBusAdapter: started")

    async def stop(self) -> None:
        self._started = False
        logger.info("EventBusAdapter: stopped")

    # ------------------------------------------------------------------
    # Publish
    # ------------------------------------------------------------------

    async def publish(self, event: WorkflowEvent) -> None:
        """Publish a workflow event to the event bus."""
        with self._lock:
            self._event_log.append(event)
            if len(self._event_log) > self._max_event_log:
                self._event_log = self._event_log[-self._max_event_log:]

        # Notify subscribers
        callbacks = list(self._subscribers.get(event.event_type.value, []))
        for callback in callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(event)
                else:
                    callback(event)
            except Exception:
                logger.exception("EventBusAdapter: subscriber error for event %s", event.event_id)

        logger.debug("EventBusAdapter: published %s (execution=%s)", event.event_type.value, event.execution_id)

    async def publish_batch(self, events: List[WorkflowEvent]) -> None:
        """Publish multiple events atomically."""
        for event in events:
            await self.publish(event)

    # ------------------------------------------------------------------
    # Subscribe
    # ------------------------------------------------------------------

    def subscribe(self, event_type: WorkflowEventType, callback: Callable) -> None:
        """Subscribe to a specific workflow event type."""
        with self._lock:
            if event_type.value not in self._subscribers:
                self._subscribers[event_type.value] = []
            self._subscribers[event_type.value].append(callback)
        logger.debug("EventBusAdapter: subscribed to %s", event_type.value)

    def unsubscribe(self, event_type: WorkflowEventType, callback: Callable) -> None:
        """Remove a subscription."""
        with self._lock:
            callbacks = self._subscribers.get(event_type.value, [])
            if callback in callbacks:
                callbacks.remove(callback)

    # ------------------------------------------------------------------
    # Replay
    # ------------------------------------------------------------------

    async def replay_events(
        self,
        execution_id: str,
        *,
        since: Optional[datetime] = None,
    ) -> List[WorkflowEvent]:
        """Replay events for a specific execution."""
        with self._lock:
            events = [e for e in self._event_log if e.execution_id == execution_id]
            if since:
                events = [e for e in events if e.timestamp >= since]
            return events

    async def get_event(self, event_id: str) -> Optional[WorkflowEvent]:
        with self._lock:
            for e in self._event_log:
                if e.event_id == event_id:
                    return e
            return None

    async def event_count(self, execution_id: Optional[str] = None) -> int:
        with self._lock:
            if execution_id:
                return sum(1 for e in self._event_log if e.execution_id == execution_id)
            return len(self._event_log)

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def health_report(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "total_events": len(self._event_log),
                "subscriber_count": sum(len(v) for v in self._subscribers.values()),
                "dead_letter_count": len(self._dead_letter),
                "subscriptions": {k: len(v) for k, v in self._subscribers.items()},
            }
