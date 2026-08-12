"""In-memory audit repository behaviour."""

from __future__ import annotations

from services.control_plane.incident.audit.event import IncidentAuditEvent
from services.control_plane.incident.audit.event_type import IncidentAuditEventType
from services.control_plane.incident.audit.repository import (
    InMemoryIncidentAuditRepository,
)


def test_audit_events_preserve_order():
    repository = InMemoryIncidentAuditRepository()
    incident_id = "INC-20260812-000001"
    first = IncidentAuditEvent(
        incident_id,
        IncidentAuditEventType.INCIDENT_CREATED,
        "system",
    )
    second = IncidentAuditEvent(
        incident_id,
        IncidentAuditEventType.INCIDENT_ACKNOWLEDGED,
        "operator-1",
    )
    repository.append(first)
    repository.append(second)

    assert repository.get(incident_id) == [first, second]


def test_get_unknown_incident_returns_empty():
    repository = InMemoryIncidentAuditRepository()
    assert repository.get("INC-20260812-999999") == []


def test_events_are_partitioned_by_incident():
    repository = InMemoryIncidentAuditRepository()
    repository.append(
        IncidentAuditEvent(
            "INC-A",
            IncidentAuditEventType.INCIDENT_CREATED,
            "system",
        )
    )
    repository.append(
        IncidentAuditEvent(
            "INC-B",
            IncidentAuditEventType.INCIDENT_CREATED,
            "system",
        )
    )
    assert len(repository.get("INC-A")) == 1
    assert len(repository.get("INC-B")) == 1
