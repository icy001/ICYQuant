"""Governance Memory – records all governance decisions for audit trail."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class GovernanceMemory:
    """Persistent record of all governance decisions, breaker events, and permission changes.

    Forms the Governance Audit Trail.
    """

    def __init__(self) -> None:
        self.events: List[Dict[str, Any]] = []

    def record(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Record a governance event.

        Args:
            event: event dict with arbitrary fields.

        Returns:
            The recorded event with timestamp.
        """
        if "timestamp" not in event:
            event["timestamp"] = datetime.now(timezone.utc).isoformat()
        self.events.append(event)
        return event

    def record_permission(self, permission: str, reason: str = "", details: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Record a permission decision."""
        return self.record({
            "type": "permission",
            "permission": permission,
            "reason": reason,
            "details": details or {},
        })

    def record_breaker(self, scope: str, target: str, action: str, reason: str = "") -> Dict[str, Any]:
        """Record a circuit breaker event."""
        return self.record({
            "type": "circuit_breaker",
            "scope": scope,
            "target": target,
            "action": action,
            "reason": reason,
        })

    def record_emergency(self, action: str, reason: str = "") -> Dict[str, Any]:
        """Record an emergency action."""
        return self.record({
            "type": "emergency",
            "action": action,
            "reason": reason,
        })

    def record_mode_change(self, from_mode: str, to_mode: str, reason: str = "") -> Dict[str, Any]:
        """Record a runtime mode change."""
        return self.record({
            "type": "mode_change",
            "from_mode": from_mode,
            "to_mode": to_mode,
            "reason": reason,
        })

    def query_by_type(self, event_type: str) -> List[Dict[str, Any]]:
        """Retrieve events by type."""
        return [e for e in self.events if e.get("type") == event_type]

    def query_recent(self, n: int = 20) -> List[Dict[str, Any]]:
        """Return most recent N events."""
        sorted_events = sorted(
            self.events,
            key=lambda e: e.get("timestamp", ""),
            reverse=True,
        )
        return sorted_events[:n]

    def query_by_timerange(self, start: str, end: str) -> List[Dict[str, Any]]:
        """Query events within ISO timestamp range."""
        return [e for e in self.events if start <= e.get("timestamp", "") <= end]

    @property
    def event_count(self) -> int:
        return len(self.events)

    def clear(self) -> None:
        self.events.clear()
