"""Shared fixtures for incident tests (Commit 27 Part 1.4)."""

from datetime import datetime, timezone

import pytest

from services.operations import (
    Incident,
    IncidentContext,
    IncidentImpact,
    IncidentSeverity,
    IncidentState,
)


@pytest.fixture
def incident():

    return Incident(
        context=IncidentContext(
            incident_id="INC-20260813-0001",
            created_at=datetime(
                2026, 8, 13, 13, 0, 0,
                tzinfo=timezone.utc,
            ),
            detected_at=datetime(
                2026, 8, 13, 13, 0, 0,
                tzinfo=timezone.utc,
            ),
            environment="production",
            source_alert_ids=(),
            trace_ids=(),
        ),
        title="Position / Ledger mismatch",
        description="Reconciliation difference detected",
        severity=IncidentSeverity.CRITICAL,
        state=IncidentState.DETECTED,
        impact=IncidentImpact(
            affected_services=("risk",),
            affected_venues=(),
            affected_strategies=(),
            affected_orders=10,
            affected_positions=2,
            trading_blocked=True,
        ),
    )
