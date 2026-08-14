"""Tests for the typed audit event model (Commit 29 Part 1.5 §5-8, §43-44)."""

from __future__ import annotations

from datetime import datetime, timezone

from services.control_plane.audit_event import (
    AuditEvent,
    AuditEventType,
    AuditTrail,
    calculate_event_hash,
)


def _event(**overrides) -> AuditEvent:
    base = dict(
        audit_id="AUD-0001",
        event_type=AuditEventType.COMMAND_CREATED,
        command_id="CMD-001",
        principal_id="operator-001",
        action="trading:pause",
        resource="trading",
        target="oms-primary",
        decision="SUBMITTED",
        reason="command_created",
        timestamp=datetime(2026, 8, 13, 9, 30, 1, tzinfo=timezone.utc),
        correlation_id="CORR-20260813-001",
        causation_id=None,
        sequence=1,
        previous_event_hash=None,
        event_hash=None,
    )
    base.update(overrides)
    return AuditEvent(**base)


def test_audit_event_carries_principal_and_context():
    event = _event()
    assert event.principal_id == "operator-001"
    assert event.action == "trading:pause"
    assert event.target == "oms-primary"
    assert event.resource == "trading"


def test_audit_event_is_frozen():
    event = _event()
    try:
        event.reason = "tampered"
    except Exception:
        pass
    else:
        raise AssertionError("AuditEvent must be immutable")


def test_causation_chain():
    timeout = _event(
        event_type=AuditEventType.EXECUTION_TIMEOUT,
        audit_id="AUD-0005",
        sequence=5,
    )
    recovery = _event(
        event_type=AuditEventType.RECOVERY_STARTED,
        audit_id="AUD-0006",
        sequence=6,
        causation_id=timeout.audit_id,
    )
    assert recovery.causation_id == timeout.audit_id


def test_calculate_event_hash_is_deterministic():
    event = _event()
    first = calculate_event_hash(event)
    second = calculate_event_hash(event)
    assert first == second
    assert len(first) == 64  # sha256 hexdigest


def test_hash_covers_previous_link():
    first = _event(audit_id="AUD-0001", sequence=1)
    second = _event(
        audit_id="AUD-0002",
        event_type=AuditEventType.AUTHORIZATION_GRANTED,
        sequence=2,
        previous_event_hash=calculate_event_hash(first),
    )
    assert calculate_event_hash(second) != calculate_event_hash(first)


def test_audit_trail_auto_hashes_and_chains():
    trail = AuditTrail()
    first = trail.record(
        event_type=AuditEventType.COMMAND_CREATED,
        command_id="CMD-001",
        principal_id="operator-001",
        action="trading:pause",
        resource="trading",
        target="oms-primary",
        decision="SUBMITTED",
        reason="command_created",
        correlation_id="CORR-20260813-001",
    )
    second = trail.record(
        event_type=AuditEventType.AUTHORIZATION_GRANTED,
        command_id="CMD-001",
        principal_id="operator-001",
        action="trading:pause",
        resource="trading",
        target="oms-primary",
        decision="ALLOW",
        reason="policy_allowed",
        correlation_id="CORR-20260813-001",
        causation_id=first.audit_id,
    )
    assert first.event_hash == calculate_event_hash(first)
    assert second.previous_event_hash == first.event_hash
    assert second.sequence == first.sequence + 1
    assert trail.verify() is True
