"""Incident model tests (Commit 27 Part 1.4, spec sections 9-10, 16-17)."""

from __future__ import annotations

from datetime import datetime, timezone

from services.operations import (
    IncidentContext,
    IncidentSeverity,
    IncidentState,
)


def test_incident_defaults(incident):

    assert incident.root_cause is None
    assert incident.assigned_to is None
    assert incident.resolved_at is None
    assert incident.closed_at is None


def test_incident_initial_state_is_detected(incident):

    assert incident.state is IncidentState.DETECTED


def test_incident_links_source_alerts(incident):

    assert incident.context.source_alert_ids == ()
    assert incident.context.environment == "production"
    assert incident.context.correlation_key is None


def test_root_cause_is_never_auto_populated(incident):
    """spec section 17: Root Cause 不允许随意自动写入。"""

    assert incident.root_cause is None


def test_incident_context_with_correlation_key():

    now = datetime.now(timezone.utc)

    context = IncidentContext(
        incident_id="INC-20260813-0001",
        created_at=now,
        detected_at=now,
        environment="production",
        source_alert_ids=("ALT-000001",),
        trace_ids=("trace-1",),
        correlation_key="venue:NASDAQ",
    )

    assert context.correlation_key == "venue:NASDAQ"
    assert context.source_alert_ids == ("ALT-000001",)
    assert context.trace_ids == ("trace-1",)


def test_incident_context_correlation_key_optional():

    now = datetime.now(timezone.utc)

    context = IncidentContext(
        incident_id="INC-20260813-0001",
        created_at=now,
        detected_at=now,
        environment="production",
        source_alert_ids=(),
        trace_ids=(),
    )

    assert context.correlation_key is None


def test_incident_severity_and_impact(incident):

    assert incident.severity is IncidentSeverity.CRITICAL
    assert incident.impact.trading_blocked is True
    assert incident.impact.affected_orders == 10
    assert incident.impact.affected_positions == 2
