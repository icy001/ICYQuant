"""Audit recorder hash-chain behaviour."""

from __future__ import annotations

from uuid import uuid4

from services.control_plane.incident.audit.event import verify_event_chain
from services.control_plane.incident.audit.event_type import IncidentAuditEventType
from services.control_plane.incident.audit.recorder import IncidentAuditRecorder
from services.control_plane.incident.audit.repository import (
    InMemoryIncidentAuditRepository,
)

INCIDENT_ID = "INC-20260812-000001"


def _recorder():
    return IncidentAuditRecorder(InMemoryIncidentAuditRepository())


def test_record_appends_signed_event():
    recorder = _recorder()
    event = recorder.record(
        INCIDENT_ID,
        IncidentAuditEventType.INCIDENT_CREATED,
        actor="system",
    )
    assert event.event_hash is not None
    assert event.previous_hash is None
    assert recorder.repository.get(INCIDENT_ID) == [event]


def test_audit_events_preserve_order():
    recorder = _recorder()
    first = recorder.record(
        INCIDENT_ID,
        IncidentAuditEventType.INCIDENT_CREATED,
        actor="system",
    )
    second = recorder.record(
        INCIDENT_ID,
        IncidentAuditEventType.INCIDENT_ACKNOWLEDGED,
        actor="operator-1",
    )
    assert recorder.repository.get(INCIDENT_ID) == [first, second]


def test_record_chains_hashes():
    recorder = _recorder()
    created = recorder.record(
        INCIDENT_ID,
        IncidentAuditEventType.INCIDENT_CREATED,
        actor="system",
    )
    acknowledged = recorder.record(
        INCIDENT_ID,
        IncidentAuditEventType.INCIDENT_ACKNOWLEDGED,
        actor="operator-1",
    )
    escalated = recorder.record(
        INCIDENT_ID,
        IncidentAuditEventType.INCIDENT_ESCALATED,
        actor="operator-1",
    )
    assert acknowledged.previous_hash == created.event_hash
    assert escalated.previous_hash == acknowledged.event_hash


def test_audit_chain_detects_tampering():
    recorder = _recorder()
    recorder.record(
        INCIDENT_ID,
        IncidentAuditEventType.INCIDENT_CREATED,
        actor="system",
    )
    recorder.record(
        INCIDENT_ID,
        IncidentAuditEventType.INCIDENT_ACKNOWLEDGED,
        actor="operator-1",
    )
    events = recorder.repository.get(INCIDENT_ID)
    assert verify_event_chain(events) is True

    # Rewrite the stored payload behind the recorder's back.
    object.__setattr__(events[0], "payload", {"description": "tampered"})
    assert verify_event_chain(events) is False


def test_record_carries_correlation_command_and_action_ids():
    recorder = _recorder()
    command_id = uuid4()
    action_id = uuid4()
    event = recorder.record(
        INCIDENT_ID,
        IncidentAuditEventType.COMMAND_CREATED,
        actor="operator-1",
        correlation_id="corr-123",
        command_id=command_id,
        action_id=action_id,
        payload={"description": "cancel open orders"},
    )
    assert event.correlation_id == "corr-123"
    assert event.command_id == command_id
    assert event.action_id == action_id
    assert event.payload["description"] == "cancel open orders"
