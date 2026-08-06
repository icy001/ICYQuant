"""Event Replication — replicates workflow events across the cluster.

Synchronizes::

    Workflow Event → Cluster → Replay Queue

Ensures that during recovery, the full event history is available so that
the recovered workflow can be restored to the exact pre-failure state.
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


class EventType(str, Enum):
    """Types of workflow events that are replicated."""

    WORKFLOW_STARTED = "workflow_started"
    WORKFLOW_COMPLETED = "workflow_completed"
    WORKFLOW_FAILED = "workflow_failed"
    NODE_STARTED = "node_started"
    NODE_COMPLETED = "node_completed"
    NODE_FAILED = "node_failed"
    VARIABLE_CHANGED = "variable_changed"
    CHECKPOINT_CREATED = "checkpoint_created"
    STATE_TRANSITION = "state_transition"


@dataclass
class ReplicatedEvent:
    """A workflow event that has been replicated across the cluster."""

    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_type: EventType = EventType.WORKFLOW_STARTED
    execution_id: str = ""
    workflow_id: str = ""
    node_id: str = ""
    source_node_id: str = ""  # The node that originated the event
    sequence_number: int = 0
    payload: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    replicated_to: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "execution_id": self.execution_id,
            "workflow_id": self.workflow_id,
            "node_id": self.node_id,
            "source_node_id": self.source_node_id,
            "sequence_number": self.sequence_number,
            "payload": dict(self.payload),
            "timestamp": self.timestamp.isoformat(),
            "replicated_to": list(self.replicated_to),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ReplicatedEvent:
        timestamp = data.get("timestamp")
        return cls(
            event_id=data.get("event_id", str(uuid.uuid4())),
            event_type=EventType(data.get("event_type", "workflow_started")),
            execution_id=data.get("execution_id", ""),
            workflow_id=data.get("workflow_id", ""),
            node_id=data.get("node_id", ""),
            source_node_id=data.get("source_node_id", ""),
            sequence_number=int(data.get("sequence_number", 0)),
            payload=dict(data.get("payload", {})),
            timestamp=datetime.fromisoformat(timestamp) if timestamp else datetime.utcnow(),
            replicated_to=list(data.get("replicated_to", [])),
            metadata=dict(data.get("metadata", {})),
        )


class EventReplication:
    """Replicates workflow events across the cluster.

    Usage::

        replication = EventReplication(replication_factor=3)
        await replication.start()
        await replication.publish(EventType.WORKFLOW_STARTED, execution_id="...", payload={...})
        events = await replication.get_events(execution_id="...")
    """

    def __init__(
        self,
        *,
        replication_factor: int = 3,
        max_events_per_execution: int = 10000,
        batch_size: int = 100,
    ) -> None:
        self._replication_factor = replication_factor
        self._max_events_per_execution = max_events_per_execution
        self._batch_size = batch_size
        self._lock = threading.RLock()
        self._started = False

        # Event store: execution_id → list of events
        self._events: Dict[str, List[ReplicatedEvent]] = {}

        # Replay queue: events to be replicated
        self._replay_queue: asyncio.Queue = asyncio.Queue()

        # Sequence counters
        self._sequences: Dict[str, int] = {}

        # Background task
        self._replay_task: Optional[asyncio.Task] = None

        # Subscribers
        self._subscribers: Dict[EventType, List[Callable]] = {}

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        self._started = True
        self._replay_task = asyncio.create_task(self._replay_loop())
        logger.info("EventReplication: started (replication_factor=%d)", self._replication_factor)

    async def stop(self) -> None:
        self._started = False
        if self._replay_task:
            self._replay_task.cancel()
            try:
                await self._replay_task
            except asyncio.CancelledError:
                pass
        logger.info("EventReplication: stopped")

    # ------------------------------------------------------------------
    # Publishing
    # ------------------------------------------------------------------

    async def publish(
        self,
        event_type: EventType,
        execution_id: str,
        *,
        workflow_id: str = "",
        node_id: str = "",
        source_node_id: str = "",
        payload: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ReplicatedEvent:
        """Publish a workflow event for cluster-wide replication."""
        with self._lock:
            seq = self._sequences.get(execution_id, 0) + 1
            self._sequences[execution_id] = seq

        event = ReplicatedEvent(
            event_type=event_type,
            execution_id=execution_id,
            workflow_id=workflow_id,
            node_id=node_id,
            source_node_id=source_node_id,
            sequence_number=seq,
            payload=payload or {},
            metadata=metadata or {},
        )

        # Store locally
        with self._lock:
            if execution_id not in self._events:
                self._events[execution_id] = []
            events = self._events[execution_id]
            events.append(event)

            # Enforce retention
            if len(events) > self._max_events_per_execution:
                self._events[execution_id] = events[-self._max_events_per_execution:]

        # Enqueue for replication to peers
        await self._replay_queue.put(event)

        # Notify local subscribers
        await self._notify_subscribers(event)

        return event

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    async def get_events(
        self,
        execution_id: str,
        *,
        since_sequence: int = 0,
        event_type: Optional[EventType] = None,
        limit: int = 1000,
    ) -> List[ReplicatedEvent]:
        """Get events for an execution, optionally filtered."""
        with self._lock:
            events = self._events.get(execution_id, [])
            results = []
            for event in events:
                if event.sequence_number <= since_sequence:
                    continue
                if event_type and event.event_type != event_type:
                    continue
                results.append(event)
                if len(results) >= limit:
                    break
            return results

    async def get_latest_sequence(self, execution_id: str) -> int:
        with self._lock:
            return self._sequences.get(execution_id, 0)

    async def get_event_count(self, execution_id: str) -> int:
        with self._lock:
            return len(self._events.get(execution_id, []))

    # ------------------------------------------------------------------
    # Replay
    # ------------------------------------------------------------------

    async def replay_events(self, execution_id: str) -> List[ReplicatedEvent]:
        """Replay all events for an execution (used during recovery)."""
        with self._lock:
            return list(self._events.get(execution_id, []))

    async def _replay_loop(self) -> None:
        """Background loop that replicates events to peer nodes."""
        while self._started:
            try:
                event = await asyncio.wait_for(self._replay_queue.get(), timeout=1.0)
                # In production: replicate to N peer nodes
                event.replicated_to.append("peer-1")  # Simulated
                logger.debug("EventReplication: replicated event %s (seq=%d)",
                             event.event_id, event.sequence_number)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("EventReplication: error in replay loop")

    # ------------------------------------------------------------------
    # Subscriptions
    # ------------------------------------------------------------------

    def subscribe(self, event_type: EventType, callback: Callable) -> None:
        """Subscribe to a specific event type."""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(callback)

    async def _notify_subscribers(self, event: ReplicatedEvent) -> None:
        callbacks = self._subscribers.get(event.event_type, [])
        for cb in callbacks:
            try:
                if asyncio.iscoroutinefunction(cb):
                    await cb(event)
                else:
                    cb(event)
            except Exception:
                logger.exception("EventReplication: subscriber error")

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    async def delete_events(self, execution_id: str) -> None:
        with self._lock:
            self._events.pop(execution_id, None)
            self._sequences.pop(execution_id, None)

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def health_report(self) -> Dict[str, Any]:
        with self._lock:
            total_events = sum(len(e) for e in self._events.values())
            return {
                "total_events": total_events,
                "executions_tracked": len(self._events),
                "replication_factor": self._replication_factor,
                "replay_queue_size": self._replay_queue.qsize(),
                "subscribers": {et.value: len(cbs) for et, cbs in self._subscribers.items()},
            }
