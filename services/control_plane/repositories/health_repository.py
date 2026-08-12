"""
HealthRepository — persistence for health monitoring data.

Stores:

    * heartbeats        (idempotent by component + instance + sequence)
    * health records    (latest HealthEvaluation projection per component)
    * health events     (HEALTH_STATUS_CHANGED / HEARTBEAT_MISSED / ...)
    * health incidents  (HealthIncident lifecycle)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from ..events.component_unresponsive import ComponentUnresponsive
from ..events.health_status_changed import HealthStatusChanged
from ..events.heartbeat_missed import HeartbeatMissed
from ..health.health_incident import HealthIncident
from ..health.health_status import HealthStatus
from ..health.heartbeat import Heartbeat, utcnow


@dataclass
class HealthRecord:
    """Latest projected health of a component."""

    component_id: str
    status: HealthStatus
    score: float
    updated_at: datetime = field(default_factory=utcnow)
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "component_id": self.component_id,
            "status": self.status.value,
            "score": self.score,
            "updated_at": self.updated_at.isoformat(),
            "details": dict(self.details),
        }


@dataclass
class HealthRepository:
    """In-memory repository with heartbeat idempotency (checksum-free)."""

    _heartbeats: Dict[Tuple[str, str], Heartbeat] = field(default_factory=dict)
    _last_sequences: Dict[Tuple[str, str], int] = field(default_factory=dict)
    _records: Dict[str, HealthRecord] = field(default_factory=dict)
    _events: List[Any] = field(default_factory=list)
    _incidents: Dict[str, HealthIncident] = field(default_factory=dict)

    # -- heartbeats ----------------------------------------------------- #

    def save_heartbeat(self, heartbeat: Heartbeat) -> bool:
        """Persist a heartbeat. Duplicates / out-of-order sequences are ignored
        and return False (idempotency by component + instance + sequence)."""
        key = (heartbeat.component_id, heartbeat.instance_id)
        last_sequence = self._last_sequences.get(key)
        if last_sequence is not None and heartbeat.sequence <= last_sequence:
            return False
        self._last_sequences[key] = heartbeat.sequence
        self._heartbeats[key] = heartbeat
        return True

    def get_last_heartbeat(
        self,
        component_id: str,
        instance_id: Optional[str] = None,
    ) -> Optional[Heartbeat]:
        if instance_id is not None:
            return self._heartbeats.get((component_id, instance_id))
        best: Optional[Heartbeat] = None
        for (cid, _iid), hb in self._heartbeats.items():
            if cid == component_id and (best is None or hb.sequence > best.sequence):
                best = hb
        return best

    def list_heartbeats(self) -> List[Heartbeat]:
        return list(self._heartbeats.values())

    def heartbeat_count(self) -> int:
        return len(self._heartbeats)

    # -- health records -------------------------------------------------- #

    def save_record(self, record: HealthRecord) -> None:
        self._records[record.component_id] = record

    def get_record(self, component_id: str) -> Optional[HealthRecord]:
        return self._records.get(component_id)

    def list_records(self) -> List[HealthRecord]:
        return list(self._records.values())

    # -- health events --------------------------------------------------- #

    def append_event(self, event: Any) -> None:
        self._events.append(event)

    def list_events(self) -> List[Any]:
        return list(self._events)

    def event_count(self) -> int:
        return len(self._events)

    # -- incidents ------------------------------------------------------- #

    def save_incident(self, incident: HealthIncident) -> None:
        self._incidents[incident.component_id] = incident

    def get_incident(self, component_id: str) -> Optional[HealthIncident]:
        return self._incidents.get(component_id)

    def list_incidents(self) -> List[HealthIncident]:
        return list(self._incidents.values())

    def incident_count(self) -> int:
        return len(self._incidents)

    # -- maintenance ------------------------------------------------------ #

    def clear(self) -> None:
        self._heartbeats.clear()
        self._last_sequences.clear()
        self._records.clear()
        self._events.clear()
        self._incidents.clear()
