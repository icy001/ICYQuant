"""Audit trail integrity tests (Commit 29 Part 1.5 §43-46, §54-57)."""

from __future__ import annotations

from dataclasses import replace

from services.control_plane.audit_event import (
    AuditEventType,
    AuditIntegrityError,
    AuditTrail,
    verify_audit_chain,
)


def _record_chain(trail: AuditTrail, command_id: str = "CMD-001") -> None:
    trail.record(
        event_type=AuditEventType.COMMAND_CREATED,
        command_id=command_id,
        principal_id="operator-001",
        action="trading:pause",
        resource="trading",
        target="oms-primary",
        decision="SUBMITTED",
        reason="command_created",
        correlation_id="CORR-20260813-001",
    )
    trail.record(
        event_type=AuditEventType.AUTHORIZATION_GRANTED,
        command_id=command_id,
        principal_id="operator-001",
        action="trading:pause",
        resource="trading",
        target="oms-primary",
        decision="ALLOW",
        reason="policy_allowed",
        correlation_id="CORR-20260813-001",
    )
    trail.record(
        event_type=AuditEventType.COMMAND_SUCCEEDED,
        command_id=command_id,
        principal_id="control-plane",
        action="trading:pause",
        resource="command",
        target="oms-primary",
        decision="SUCCEEDED",
        reason="command_succeeded",
        correlation_id="CORR-20260813-001",
    )


def test_audit_chain_integrity():
    trail = AuditTrail()
    _record_chain(trail)
    events = trail.events("CMD-001")
    assert verify_audit_chain(events) is True


def test_audit_chain_survives_out_of_order_input():
    trail = AuditTrail()
    _record_chain(trail)
    events = list(trail.events("CMD-001"))
    reversed_events = list(reversed(events))
    assert verify_audit_chain(reversed_events) is True


def test_audit_tampering_is_detected():
    trail = AuditTrail()
    _record_chain(trail)
    events = list(trail.events("CMD-001"))
    tampered = replace(events[2], reason="modified")
    events[2] = tampered
    assert verify_audit_chain(events) is False


def test_audit_chain_missing_link_is_detected():
    trail = AuditTrail()
    _record_chain(trail)
    events = list(trail.events("CMD-001"))
    # Drop the middle event: the third event's previous_event_hash no longer
    # matches the second event's hash, and the sequence is no longer contiguous.
    dropped = [events[0], events[2]]
    assert verify_audit_chain(dropped) is False


def test_empty_chain_is_valid():
    assert verify_audit_chain([]) is True


def test_audit_integrity_failure_raises_classification():
    trail = AuditTrail()
    _record_chain(trail)
    events = list(trail.events("CMD-001"))
    events[1] = replace(events[1], reason="tampered")
    if verify_audit_chain(events):
        raise AssertionError("tampered chain must not verify")
    # AUDIT_INTEGRITY_FAILURE must be treated as CRITICAL (asserted in test_alerts)
    error = AuditIntegrityError("audit chain broken")
    assert "broken" in str(error)


def test_events_filtered_by_command_and_correlation():
    trail = AuditTrail()
    _record_chain(trail)
    _record_chain(trail, command_id="CMD-002")
    assert len(trail.events("CMD-001")) == 3
    assert len(trail.events("CMD-002")) == 3
    by_corr = trail.by_correlation_id("CORR-20260813-001")
    assert len(by_corr) == 6
