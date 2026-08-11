"""
Immutable Audit Log — append-only log of governance audit events.

Core principle: Audit Events are append-only. Once written, they cannot
be modified or deleted. Corrections are new events, not modifications.
"""

from __future__ import annotations

import threading
from collections import defaultdict
from typing import Any, Dict, List, Optional

from .audit_event import AuditEvent
from .audit_event_type import AuditEventType


class ImmutableAuditLog:
    """Append-only, thread-safe log of AuditEvent records.

    Cannot UPDATE or DELETE existing records.
    Supports indexed queries by correlation_id, entity, event type.
    """

    def __init__(self, max_events: int = 1_000_000):
        self._events: List[AuditEvent] = []
        self._lock = threading.Lock()
        self._max_events = max_events

        # Indices
        self._by_correlation: Dict[str, List[int]] = defaultdict(list)
        self._by_entity: Dict[str, List[int]] = defaultdict(list)
        self._by_type: Dict[str, List[int]] = defaultdict(list)
        self._by_actor: Dict[str, List[int]] = defaultdict(list)

    def record(self, event: AuditEvent) -> int:
        """Append an event to the immutable log. Returns its index."""
        with self._lock:
            if len(self._events) >= self._max_events:
                # Evict oldest (or raise — implementation choice)
                self._events.pop(0)
                self._reindex()

            idx = len(self._events)
            self._events.append(event)
            self._index_event(idx, event)
            return idx

    def record_batch(self, events: List[AuditEvent]) -> List[int]:
        """Append multiple events atomically."""
        with self._lock:
            indices: List[int] = []
            for event in events:
                if len(self._events) >= self._max_events:
                    self._events.pop(0)
                    self._reindex()
                idx = len(self._events)
                self._events.append(event)
                self._index_event(idx, event)
                indices.append(idx)
            return indices

    # ── Query ──

    def query_by_correlation(self, correlation_id: str) -> List[AuditEvent]:
        indices = self._by_correlation.get(correlation_id, [])
        return self._get_events(indices)

    def query_by_entity(self, entity_type: str, entity_id: str) -> List[AuditEvent]:
        key = f"{entity_type}:{entity_id}"
        indices = self._by_entity.get(key, [])
        return self._get_events(indices)

    def query_by_type(self, event_type: AuditEventType, limit: int = 100) -> List[AuditEvent]:
        key = event_type.name if isinstance(event_type, AuditEventType) else str(event_type)
        indices = self._by_type.get(key, [])[:limit]
        return self._get_events(indices)

    def query_by_actor(self, actor_id: str) -> List[AuditEvent]:
        indices = self._by_actor.get(actor_id, [])
        return self._get_events(indices)

    def query_time_range(
        self, start: float, end: float, limit: int = 1000
    ) -> List[AuditEvent]:
        results: List[AuditEvent] = []
        with self._lock:
            for event in reversed(self._events):
                if start <= event.timestamp <= end:
                    results.append(event)
                    if len(results) >= limit:
                        break
        return list(reversed(results))

    def query_all(self, limit: int = 1000) -> List[AuditEvent]:
        with self._lock:
            return list(self._events[-limit:])

    # ── Properties ──

    @property
    def size(self) -> int:
        with self._lock:
            return len(self._events)

    @property
    def last_event(self) -> Optional[AuditEvent]:
        with self._lock:
            return self._events[-1] if self._events else None

    @property
    def is_empty(self) -> bool:
        return self.size == 0

    # ── Internal ──

    def _index_event(self, idx: int, event: AuditEvent) -> None:
        if event.correlation_id:
            self._by_correlation[event.correlation_id].append(idx)
        entity_key = f"{event.entity_type}:{event.entity_id}"
        self._by_entity[entity_key].append(idx)
        self._by_type[event.event_type.name].append(idx)
        ai = event.actor.actor_id
        if ai:
            self._by_actor[ai].append(idx)

    def _reindex(self) -> None:
        """Full reindex (used after eviction)."""
        self._by_correlation.clear()
        self._by_entity.clear()
        self._by_type.clear()
        self._by_actor.clear()
        for idx, event in enumerate(self._events):
            self._index_event(idx, event)

    def _get_events(self, indices: List[int]) -> List[AuditEvent]:
        with self._lock:
            return [self._events[i] for i in indices if 0 <= i < len(self._events)]
