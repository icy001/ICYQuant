"""Audit event immutability, hashing and chain verification."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from uuid import UUID

import pytest

from services.control_plane.incident.audit.event import (
    IncidentAuditEvent,
    calculate_event_hash,
    event_payload,
    verify_event_chain,
)
from services.control_plane.incident.audit.event_type import IncidentAuditEventType

INCIDENT_ID = "INC-20260812-000001"


def _chained(events):
    """Sign a list of events so every event_hash links to its predecessor."""
    signed = []
    previous_hash = None
    for event in events:
        staged = replace(event, previous_hash=previous_hash)
        staged = replace(
            staged,
            event_hash=calculate_event_hash(
                event_payload(staged),
                previous_hash,
            ),
        )
        signed.append(staged)
        previous_hash = staged.event_hash
    return signed


def test_audit_event_is_immutable():
    event = IncidentAuditEvent(
        incident_id=INCIDENT_ID,
        event_type=IncidentAuditEventType.INCIDENT_CREATED,
        actor="system",
    )
    with pytest.raises(FrozenInstanceError):
        event.actor = "someone-else"


def test_audit_event_contains_actor():
    event = IncidentAuditEvent(
        incident_id=INCIDENT_ID,
        event_type=IncidentAuditEventType.INCIDENT_CREATED,
        actor="detection-engine",
    )
    assert event.actor == "detection-engine"


def test_audit_event_has_generated_identity_and_utc_timestamp():
    event = IncidentAuditEvent(
        incident_id=INCIDENT_ID,
        event_type=IncidentAuditEventType.INCIDENT_CREATED,
        actor="system",
    )
    assert isinstance(event.event_id, UUID)
    assert event.timestamp.tzinfo is not None


def test_calculate_event_hash_is_deterministic():
    payload = {"description": "hello", "count": 1}
    assert calculate_event_hash(payload, None) == calculate_event_hash(payload, None)


def test_calculate_event_hash_links_previous_hash():
    payload = {"description": "hello"}
    first = calculate_event_hash(payload, None)
    second = calculate_event_hash(payload, first)
    assert first != second
    assert calculate_event_hash(payload, "tampered") != second


def test_verify_event_chain_accepts_signed_chain():
    events = _chained(
        [
            IncidentAuditEvent(
                INCIDENT_ID,
                IncidentAuditEventType.INCIDENT_CREATED,
                "system",
            ),
            IncidentAuditEvent(
                INCIDENT_ID,
                IncidentAuditEventType.INCIDENT_ACKNOWLEDGED,
                "operator-1",
            ),
        ]
    )
    assert verify_event_chain(events) is True


def test_verify_event_chain_detects_tampering():
    events = _chained(
        [
            IncidentAuditEvent(
                INCIDENT_ID,
                IncidentAuditEventType.INCIDENT_CREATED,
                "system",
            ),
            IncidentAuditEvent(
                INCIDENT_ID,
                IncidentAuditEventType.INCIDENT_ACKNOWLEDGED,
                "operator-1",
            ),
            IncidentAuditEvent(
                INCIDENT_ID,
                IncidentAuditEventType.INCIDENT_ESCALATED,
                "operator-1",
            ),
        ]
    )
    assert verify_event_chain(events) is True
    # Simulate a tampered store: payload rewritten behind the recorder's back.
    object.__setattr__(events[1], "payload", {"description": "tampered"})
    assert verify_event_chain(events) is False
