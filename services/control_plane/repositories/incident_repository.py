"""
IncidentRepository — persistent store for the Incident Management domain.

An incident is long-lived Control Plane state, not a log line: it must survive
queries for open incidents, fingerprint deduplication, scope/severity filters
and full audit replay (spec section 21).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union

from ..incident.incident import Incident
from ..incident.incident_fingerprint import IncidentFingerprint
from ..incident.incident_id import IncidentId
from ..incident.incident_scope import IncidentScope
from ..incident.incident_severity import IncidentSeverity
from ..incident.incident_status import IncidentStatus


@dataclass
class IncidentRepository:
    """In-memory store of incidents and incident lifecycle events."""

    _incidents: List[Dict[str, Any]] = field(default_factory=list)
    _events: List[Any] = field(default_factory=list)

    # -- writes ----------------------------------------------------------

    def save(self, incident: Incident) -> None:
        """Upsert an incident by id."""
        for i, existing in enumerate(self._incidents):
            if existing["incident_id"] == incident.incident_id.value:
                self._incidents[i] = incident.to_dict()
                return
        self._incidents.append(incident.to_dict())

    create = save

    def update(self, incident: Incident) -> None:
        self.save(incident)

    def append_event(self, event: Any) -> None:
        self._events.append(event)

    # -- queries ---------------------------------------------------------

    def get(self, incident_id: Union[IncidentId, str]) -> Optional[Incident]:
        incident_id = incident_id if isinstance(incident_id, IncidentId) else IncidentId(incident_id)
        for data in self._incidents:
            if data["incident_id"] == incident_id.value:
                return Incident.from_dict(data)
        return None

    find_by_id = get

    def list_all(self) -> List[Incident]:
        return [Incident.from_dict(d) for d in self._incidents]

    def find_open(self) -> List[Incident]:
        return [
            Incident.from_dict(d)
            for d in self._incidents
            if IncidentStatus(d["status"]).is_open
        ]

    def find_by_fingerprint(self, fingerprint: IncidentFingerprint) -> List[Incident]:
        """All incidents (open + closed) that share this fingerprint."""
        results = []
        for data in self._incidents:
            fp = data.get("fingerprint")
            if fp is None:
                continue
            if IncidentFingerprint.from_dict(fp) == fingerprint:
                results.append(Incident.from_dict(data))
        return results

    def find_active_by_fingerprint(self, fingerprint: IncidentFingerprint) -> Optional[Incident]:
        """The open incident matching this fingerprint, if any (dedup target)."""
        for data in self._incidents:
            fp = data.get("fingerprint")
            if fp is None:
                continue
            if (
                IncidentFingerprint.from_dict(fp) == fingerprint
                and IncidentStatus(data["status"]).is_open
            ):
                return Incident.from_dict(data)
        return None

    def find_by_scope(self, scope: IncidentScope) -> List[Incident]:
        return [
            Incident.from_dict(d)
            for d in self._incidents
            if IncidentScope(d["scope"]) is scope
        ]

    def find_by_severity(self, severity: IncidentSeverity) -> List[Incident]:
        return [
            Incident.from_dict(d)
            for d in self._incidents
            if IncidentSeverity(d["severity"]) is severity
        ]

    def find_by_source(self, source: Any) -> List[Incident]:
        from ..incident.incident_source import IncidentSource

        source = IncidentSource(source)
        return [
            Incident.from_dict(d)
            for d in self._incidents
            if IncidentSource(d["source"]) is source
        ]

    def list_events(self) -> List[Any]:
        return list(self._events)

    def event_count(self) -> int:
        return len(self._events)

    def incident_count(self) -> int:
        return len(self._incidents)

    def open_count(self) -> int:
        return len(self.find_open())

    def critical_count(self) -> int:
        return sum(
            1
            for d in self._incidents
            if IncidentSeverity(d["severity"]) >= IncidentSeverity.CRITICAL
            and IncidentStatus(d["status"]).is_open
        )

    def clear(self) -> None:
        self._incidents.clear()
        self._events.clear()
