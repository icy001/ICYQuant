"""Diagnostics tests: redaction, snapshot and timeline (Commit 29 Part 1.5 §32-34, §39-41, §61)."""

from __future__ import annotations

from datetime import datetime, timezone

from services.control_plane.diagnostics import (
    REDACTED,
    ControlPlaneDiagnostics,
    redact,
)
from services.control_plane.event import InMemoryEventStore
from services.control_plane.metrics import ControlMetrics


def test_sensitive_fields_are_redacted():
    payload = {"token": "secret-token"}
    result = redact(payload)
    assert result["token"] == "[REDACTED]"


def test_nested_payload_is_redacted_recursively():
    payload = {
        "reason": "risk breach",
        "api_key": "sk_live_123",
        "parameters": {"account": "A-1", "password": "hunter2"},
    }
    result = redact(payload)
    assert result["reason"] == "risk breach"
    assert result["api_key"] == "[REDACTED]"
    assert result["parameters"]["password"] == "[REDACTED]"
    assert result["parameters"]["account"] == "A-1"


def test_list_of_mappings_is_redacted():
    result = redact({"items": [{"token": "x"}, {"value": 1}]})
    assert result["items"][0]["token"] == "[REDACTED]"
    assert result["items"][1]["value"] == 1


def test_original_payload_is_not_mutated():
    payload = {"token": "secret", "name": "ops"}
    result = redact(payload)
    assert payload["token"] == "secret"
    assert result != payload


def test_diagnostics_snapshot_counts_states():
    metrics = ControlMetrics()
    metrics.record_submitted()
    metrics.record_duplicate()
    metrics.record_executed()
    metrics.record_timeout()

    diagnostics = ControlPlaneDiagnostics(
        command_states=[
            "EXECUTING",
            "EXECUTING",
            "UNKNOWN",
            "RECOVERY_REQUIRED",
            "FAILED",
            "SUCCEEDED",
        ],
        claims=[{"state": "ACTIVE"}, {"state": "EXPIRED"}, {"state": "ACTIVE"}],
        metrics=metrics,
    )
    snapshot = diagnostics.snapshot()
    assert snapshot.active_commands == 5
    assert snapshot.executing_commands == 2
    assert snapshot.unknown_commands == 1
    assert snapshot.recovery_commands == 1
    assert snapshot.failed_commands == 1
    assert snapshot.active_claims == 2
    assert snapshot.expired_claims == 1
    assert snapshot.duplicate_rate == 1.0
    assert snapshot.timeout_rate == 1.0


def test_timeline_rebuilds_command_order():
    store = InMemoryEventStore()
    for event_type in (
        "COMMAND_CREATED",
        "AUTHORIZATION_GRANTED",
        "COMMAND_DISPATCHED",
        "EXECUTION_STARTED",
        "EXECUTION_TIMEOUT",
        "RECOVERY_STARTED",
        "TARGET_RECONCILED",
        "COMMAND_SUCCEEDED",
    ):
        store.append(
            event_type=event_type,
            command_id="CMD-001",
            correlation_id="CORR-001",
        )

    diagnostics = ControlPlaneDiagnostics(
        events_provider=lambda command_id: store.events(command_id)
    )
    timeline = diagnostics.timeline("CMD-001")
    assert len(timeline) == 8
    assert [entry.event_type for entry in timeline] == [
        "COMMAND_CREATED",
        "AUTHORIZATION_GRANTED",
        "COMMAND_DISPATCHED",
        "EXECUTION_STARTED",
        "EXECUTION_TIMEOUT",
        "RECOVERY_STARTED",
        "TARGET_RECONCILED",
        "COMMAND_SUCCEEDED",
    ]
    assert all(isinstance(entry.timestamp, datetime) for entry in timeline)
    assert timeline[-1].timestamp.tzinfo is timezone.utc


def test_timeline_handles_out_of_order_sequence():
    store = InMemoryEventStore()
    first = store.append(
        event_type="COMMAND_CREATED", command_id="CMD-001", correlation_id="C"
    )
    second = store.append(
        event_type="COMMAND_SUCCEEDED", command_id="CMD-001", correlation_id="C"
    )
    assert second.sequence > first.sequence

    diagnostics = ControlPlaneDiagnostics(
        events_provider=lambda command_id: store.events(command_id)
    )
    timeline = diagnostics.timeline("CMD-001")
    assert [entry.event_type for entry in timeline] == [
        "COMMAND_CREATED",
        "COMMAND_SUCCEEDED",
    ]


def test_timeline_without_provider_is_empty():
    diagnostics = ControlPlaneDiagnostics()
    assert diagnostics.timeline("CMD-001") == ()
