"""
Governance Event Store — persistent store for governance events.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .governance_event import GovernanceEvent, GovernanceEventType


class GovernanceEventStore:
    """
    In-memory event store for governance events.
    Supports append, query, and replay-like operations.
    """

    def __init__(self, max_events: int = 100000):
        self._events: List[GovernanceEvent] = []
        self._max_events = max_events

    # ------------------------------------------------------------------
    # Append
    # ------------------------------------------------------------------

    def append(self, event: GovernanceEvent) -> None:
        self._events.append(event)
        if len(self._events) > self._max_events:
            self._events = self._events[-self._max_events:]

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_by_decision(self, decision_id: str) -> List[GovernanceEvent]:
        """Get all events for a specific decision."""
        return [e for e in self._events if e.decision_id == decision_id]

    def get_by_request(self, request_id: str) -> List[GovernanceEvent]:
        """Get all events for a specific request."""
        return [e for e in self._events if e.request_id == request_id]

    def get_by_type(self, event_type: GovernanceEventType, limit: int = 100) -> List[GovernanceEvent]:
        """Get events of a specific type."""
        results = []
        for e in reversed(self._events):
            if e.event_type == event_type:
                results.append(e)
                if len(results) >= limit:
                    break
        return list(reversed(results))

    def get_by_actor(self, actor: str, limit: int = 100) -> List[GovernanceEvent]:
        """Get events for a specific actor."""
        results = []
        for e in reversed(self._events):
            if e.actor == actor:
                results.append(e)
                if len(results) >= limit:
                    break
        return list(reversed(results))

    def get_recent(self, n: int = 50) -> List[GovernanceEvent]:
        """Get most recent events."""
        return self._events[-n:]

    def get_errors(self, limit: int = 50) -> List[GovernanceEvent]:
        """Get error events."""
        return self.get_by_type(GovernanceEventType.GOVERNANCE_ERROR, limit=limit)

    # ------------------------------------------------------------------
    # Replay
    # ------------------------------------------------------------------

    def replay_decision(self, decision_id: str) -> List[Dict[str, Any]]:
        """Replay the event sequence for a decision."""
        events = self.get_by_decision(decision_id)
        return [e.to_dict() for e in sorted(events, key=lambda e: e.timestamp)]

    def decision_trace(self, decision_id: str) -> List[str]:
        """Get the event type sequence for a decision."""
        events = self.get_by_decision(decision_id)
        return [e.event_type.name for e in sorted(events, key=lambda e: e.timestamp)]

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def count(self) -> int:
        return len(self._events)

    def type_counts(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for e in self._events:
            name = e.event_type.name
            counts[name] = counts.get(name, 0) + 1
        return counts

    def clear(self) -> None:
        self._events.clear()
