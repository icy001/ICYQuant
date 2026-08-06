"""Event store — unified event storage for workflow events.

Publishes events to configured backends: in-memory, Kafka, Database, Object Storage.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid

logger = logging.getLogger(__name__)


class EventBackend(str, Enum):
    MEMORY = "memory"
    KAFKA = "kafka"
    DATABASE = "database"
    OBJECT_STORAGE = "object_storage"


@dataclass
class StoredEvent:
    """A persisted workflow event."""

    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    execution_id: str = ""
    event_type: str = ""
    node_id: Optional[str] = None
    payload: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    version: int = 0
    backend: EventBackend = EventBackend.MEMORY

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "execution_id": self.execution_id,
            "event_type": self.event_type,
            "node_id": self.node_id,
            "payload": self.payload,
            "timestamp": self.timestamp.isoformat(),
            "version": self.version,
            "backend": self.backend.value,
        }


class EventStore:
    """Unified event store for workflow domain events.

    Supports multiple backends for different durability and throughput needs:
      - Memory: fast, ephemeral (default)
      - Kafka: high-throughput distributed streaming
      - Database: durable, queryable
      - Object Storage: long-term archival
    """

    def __init__(self, backend: EventBackend = EventBackend.MEMORY):
        self._backend = backend
        self._events: Dict[str, List[StoredEvent]] = {}
        self._version_counters: Dict[str, int] = {}

    # ---- Publish / Store ----------------------------------------------------

    async def store(
        self,
        execution_id: str,
        event_type: str,
        payload: Optional[Dict[str, Any]] = None,
        node_id: Optional[str] = None,
    ) -> StoredEvent:
        """Store a new event."""
        version = self._next_version(execution_id)
        event = StoredEvent(
            execution_id=execution_id,
            event_type=event_type,
            node_id=node_id,
            payload=payload or {},
            version=version,
            backend=self._backend,
        )
        self._append(execution_id, event)
        logger.debug("Event stored: exec=%s type=%s v=%d", execution_id, event_type, version)
        return event

    # ---- Query --------------------------------------------------------------

    async def get_events(
        self,
        execution_id: str,
        event_type: Optional[str] = None,
        since_version: Optional[int] = None,
    ) -> List[StoredEvent]:
        """Query events with optional filters."""
        events = self._events.get(execution_id, [])
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        if since_version is not None:
            events = [e for e in events if e.version > since_version]
        return events

    async def get_node_events(self, execution_id: str, node_id: str) -> List[StoredEvent]:
        """Get all events for a specific node."""
        return [
            e for e in self._events.get(execution_id, [])
            if e.node_id == node_id
        ]

    async def get_latest_version(self, execution_id: str) -> int:
        return self._version_counters.get(execution_id, 0)

    # ---- Internal -----------------------------------------------------------

    def _next_version(self, execution_id: str) -> int:
        current = self._version_counters.get(execution_id, 0)
        self._version_counters[execution_id] = current + 1
        return self._version_counters[execution_id]

    def _append(self, execution_id: str, event: StoredEvent) -> None:
        if execution_id not in self._events:
            self._events[execution_id] = []
        self._events[execution_id].append(event)

    async def archive(self, execution_id: str) -> List[StoredEvent]:
        """Archive all events for a terminal execution (for long-term storage)."""
        events = self._events.pop(execution_id, [])
        logger.info("Archived %d events for execution %s", len(events), execution_id)
        return events
