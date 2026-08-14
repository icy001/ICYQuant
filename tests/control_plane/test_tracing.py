"""Control tracing tests (Commit 29 Part 1.5 §29-32)."""

from __future__ import annotations

from services.control_plane.tracing import ControlTrace


def test_start_span_records_attributes():
    trace = ControlTrace()
    span = trace.start_span(
        "control.command",
        {"command_id": "CMD-001", "target": "oms-primary"},
    )
    assert span.name == "control.command"
    assert span.attributes["command_id"] == "CMD-001"
    assert len(trace.spans()) == 1


def test_span_finish_records_duration():
    from datetime import datetime, timedelta, timezone

    trace = ControlTrace()
    span = trace.start_span("control.execution", {})
    trace.end_span(span, ended_at=span.started_at + timedelta(milliseconds=50))
    assert span.ended_at is not None
    assert span.duration_seconds is not None
    assert abs(span.duration_seconds - 0.05) < 1e-9


def test_parent_child_relationship():
    trace = ControlTrace()
    root = trace.start_span("control.command", {}, trace_id="TRACE-X")
    child = trace.start_span("control.authorization", {}, parent=root)
    assert child.trace_id == root.trace_id
    assert child.parent_span_id == root.span_id


def test_spans_filtered_by_trace():
    trace = ControlTrace()
    trace.start_span("control.command", {"command_id": "CMD-001"})
    trace.start_span("control.command", {"command_id": "CMD-002"})
    first = trace.spans()[0]
    assert len(trace.spans(first.trace_id)) == 1
    assert len(trace.spans()) == 2


def test_sensitive_attributes_are_redacted():
    trace = ControlTrace()
    span = trace.start_span(
        "control.execution",
        {"command_id": "CMD-001", "token": "sk_live_secret", "api_key": "abcd"},
    )
    assert span.attributes["token"] == "[REDACTED]"
    assert span.attributes["api_key"] == "[REDACTED]"
    assert "sk_live_secret" not in str(trace.to_dict())


def test_nested_sensitive_attributes_are_redacted():
    trace = ControlTrace()
    span = trace.start_span(
        "control.execution",
        {"command_id": "CMD-001", "credentials": {"password": "p@ss", "user": "ops"}},
    )
    assert span.attributes["credentials"]["password"] == "[REDACTED]"
    assert span.attributes["credentials"]["user"] == "ops"


def test_trace_to_dict_round_trip():
    trace = ControlTrace()
    trace.start_span("control.command", {"command_id": "CMD-001"})
    dump = trace.to_dict()
    assert len(dump) == 1
    assert dump[0]["name"] == "control.command"
