"""Incident audit service facade."""

from __future__ import annotations

from services.control_plane.incident.audit.event_type import IncidentAuditEventType
from services.control_plane.incident.audit.recorder import IncidentAuditRecorder
from services.control_plane.incident.audit.repository import (
    InMemoryIncidentAuditRepository,
)
from services.control_plane.incident.audit.service import IncidentAuditService

INCIDENT_ID = "INC-20260812-000001"


def _service():
    recorder = IncidentAuditRecorder(InMemoryIncidentAuditRepository())
    return IncidentAuditService(recorder)


def test_service_records_and_reads_timeline():
    service = _service()
    created = service.record(
        INCIDENT_ID,
        IncidentAuditEventType.INCIDENT_CREATED,
        actor="system",
    )
    acknowledged = service.record(
        INCIDENT_ID,
        IncidentAuditEventType.INCIDENT_ACKNOWLEDGED,
        actor="operator-1",
    )
    assert service.timeline(INCIDENT_ID) == [created, acknowledged]


def test_audit_event_contains_actor():
    service = _service()
    event = service.record(
        INCIDENT_ID,
        IncidentAuditEventType.INCIDENT_ACKNOWLEDGED,
        actor="operator-1",
    )
    assert event.actor == "operator-1"


def test_service_timeline_empty_for_unknown_incident():
    service = _service()
    assert service.timeline("INC-20260812-999999") == []
