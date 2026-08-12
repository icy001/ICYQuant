"""Timeline reconstruction from audit events."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from services.control_plane.incident.audit.event import IncidentAuditEvent
from services.control_plane.incident.audit.event_type import IncidentAuditEventType
from services.control_plane.incident.postmortem.timeline import (
    IncidentTimelineBuilder,
)

INCIDENT_ID = "INC-20260812-000001"
T0 = datetime(2026, 8, 12, 9, 31, 2, tzinfo=timezone.utc)


def _event(event_type, timestamp, actor, **payload):
    return IncidentAuditEvent(
        incident_id=INCIDENT_ID,
        event_type=event_type,
        actor=actor,
        timestamp=timestamp,
        payload=payload,
    )


def test_timeline_is_sorted_by_timestamp():
    events = [
        _event(
            IncidentAuditEventType.INCIDENT_ACKNOWLEDGED,
            T0 + timedelta(seconds=3),
            "operator-1",
        ),
        _event(
            IncidentAuditEventType.INCIDENT_CREATED,
            T0,
            "system",
        ),
        _event(
            IncidentAuditEventType.INCIDENT_ESCALATED,
            T0 + timedelta(seconds=1),
            "operator-1",
        ),
    ]
    entries = IncidentTimelineBuilder().build(events)
    assert [entry.event_type for entry in entries] == [
        "INCIDENT_CREATED",
        "INCIDENT_ESCALATED",
        "INCIDENT_ACKNOWLEDGED",
    ]


def test_timeline_contains_all_incident_events():
    events = [
        _event(
            IncidentAuditEventType.INCIDENT_CREATED,
            T0,
            "system",
        ),
        _event(
            IncidentAuditEventType.INCIDENT_ACKNOWLEDGED,
            T0 + timedelta(seconds=1),
            "operator-1",
        ),
        _event(
            IncidentAuditEventType.INCIDENT_RESOLVED,
            T0 + timedelta(seconds=24),
            "operator-1",
        ),
    ]
    entries = IncidentTimelineBuilder().build(events)
    assert len(entries) == 3
    assert {entry.event_type for entry in entries} == {
        "INCIDENT_CREATED",
        "INCIDENT_ACKNOWLEDGED",
        "INCIDENT_RESOLVED",
    }


def test_timeline_description_prefers_payload():
    events = [
        _event(
            IncidentAuditEventType.INCIDENT_CREATED,
            T0,
            "system",
            description="system detected failure",
        ),
        _event(
            IncidentAuditEventType.INCIDENT_ACKNOWLEDGED,
            T0 + timedelta(seconds=1),
            "operator-1",
        ),
    ]
    entries = IncidentTimelineBuilder().build(events)
    assert entries[0].description == "system detected failure"
    assert entries[1].description == "INCIDENT_ACKNOWLEDGED"
