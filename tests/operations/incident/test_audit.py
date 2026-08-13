"""Incident audit tests (Commit 27 Part 1.4, spec sections 26-27, 40)."""

from __future__ import annotations

import dataclasses
from datetime import datetime, timedelta, timezone

import pytest

from services.operations import (
    IncidentAuditEvent,
    IncidentAuditLog,
)


def test_audit_records_transition():
    # spec section 40
    event = IncidentAuditEvent(
        incident_id="INC-001",
        event_type="STATE_CHANGED",
        timestamp=datetime.now(timezone.utc),
        actor="incident-engine",
        previous_state="DETECTED",
        new_state="TRIAGED",
        reason="automatic triage",
        metadata={},
    )

    assert event.incident_id == "INC-001"
    assert event.new_state == "TRIAGED"
    assert event.previous_state == "DETECTED"
    assert event.actor == "incident-engine"


def test_audit_event_is_frozen():

    event = IncidentAuditEvent(
        incident_id="INC-001",
        event_type="INCIDENT_CREATED",
        timestamp=datetime.now(timezone.utc),
        actor="incident-engine",
        previous_state=None,
        new_state=None,
        reason="incident created",
        metadata={},
    )

    with pytest.raises(dataclasses.FrozenInstanceError):

        event.reason = "changed"


def test_audit_log_records_and_filters_by_incident():

    log = IncidentAuditLog()

    log.record(
        IncidentAuditEvent(
            incident_id="INC-001",
            event_type="INCIDENT_CREATED",
            timestamp=datetime(
                2026, 8, 13, 13, 1, 2,
                tzinfo=timezone.utc,
            ),
            actor="incident-engine",
            previous_state=None,
            new_state="DETECTED",
            reason="incident created",
            metadata={},
        )
    )

    log.record(
        IncidentAuditEvent(
            incident_id="INC-002",
            event_type="INCIDENT_CREATED",
            timestamp=datetime(
                2026, 8, 13, 13, 2, 0,
                tzinfo=timezone.utc,
            ),
            actor="incident-engine",
            previous_state=None,
            new_state="DETECTED",
            reason="incident created",
            metadata={},
        )
    )

    assert len(log.events_for("INC-001")) == 1
    assert len(log.all_events()) == 2
    assert log.events_for("INC-unknown") == ()


def test_audit_log_timeline_is_chronological():

    log = IncidentAuditLog()

    base = datetime(2026, 8, 13, 13, 1, 0, tzinfo=timezone.utc)

    log.record(
        IncidentAuditEvent(
            incident_id="INC-001",
            event_type="LATE",
            timestamp=base + timedelta(seconds=5),
            actor="a",
            previous_state=None,
            new_state=None,
            reason="",
            metadata={},
        )
    )

    log.record(
        IncidentAuditEvent(
            incident_id="INC-001",
            event_type="EARLY",
            timestamp=base + timedelta(seconds=1),
            actor="a",
            previous_state=None,
            new_state=None,
            reason="",
            metadata={},
        )
    )

    events = log.timeline("INC-001")

    assert [event.event_type for event in events] == [
        "EARLY",
        "LATE",
    ]


def test_audit_log_empty_timeline():

    assert IncidentAuditLog().timeline("INC-unknown") == ()
