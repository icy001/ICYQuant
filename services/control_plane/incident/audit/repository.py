"""
InMemoryIncidentAuditRepository — append-only per-incident audit log.

Production can swap this for PostgreSQL + Event Store + Object Storage without
changing the recorder/service API (spec section 5).
"""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, List

from .event import IncidentAuditEvent


class InMemoryIncidentAuditRepository:
    """Append-only in-memory audit store keyed by incident id."""

    def __init__(self) -> None:
        self._events: Dict[str, List[IncidentAuditEvent]] = defaultdict(list)

    def append(self, event: IncidentAuditEvent) -> None:
        """Append one immutable event; ordering is append order."""
        self._events[event.incident_id].append(event)

    def get(self, incident_id: str) -> List[IncidentAuditEvent]:
        """Return all events for an incident in append order."""
        return list(self._events.get(incident_id, []))
