"""
Tests for Alert model (Commit 27 Part 1.3, spec section 6).

Alert 是"发现异常"，不是"执行交易控制"。
"""

from __future__ import annotations

import dataclasses
from datetime import datetime, timezone

import pytest

from services.operations import (
    Alert,
    AlertSeverity,
    AlertState,
)


def _alert() -> Alert:
    return Alert(
        alert_id="ALT-000001",
        rule_id="execution-latency-high",
        severity=AlertSeverity.WARNING,
        state=AlertState.FIRING,
        title="Execution latency high",
        message="execution_latency_ms = 120 > 100",
        service_id="execution",
        labels={"venue": "NASDAQ"},
        fired_at=datetime(2026, 8, 13, 0, 0, 0, tzinfo=timezone.utc),
    )


def test_alert_fields():
    alert = _alert()

    assert alert.alert_id == "ALT-000001"
    assert alert.rule_id == "execution-latency-high"
    assert alert.severity is AlertSeverity.WARNING
    assert alert.state is AlertState.FIRING
    assert alert.service_id == "execution"
    assert alert.labels == {"venue": "NASDAQ"}


def test_alert_defaults():
    alert = _alert()

    assert alert.resolved_at is None
    assert alert.incident_id is None


def test_alert_is_frozen():
    alert = _alert()

    with pytest.raises(dataclasses.FrozenInstanceError):
        alert.state = AlertState.ACKNOWLEDGED


def test_alert_supports_lifecycle_fields():
    """spec section 19: RESOLVED 可记录 resolved_at，可关联 incident。"""
    alert = Alert(
        alert_id="ALT-000002",
        rule_id="reconciliation-difference",
        severity=AlertSeverity.CRITICAL,
        state=AlertState.RESOLVED,
        title="Position reconciliation difference",
        message="differences = 1 > 0",
        service_id="reconciliation",
        labels={},
        fired_at=datetime(2026, 8, 13, 0, 0, 0, tzinfo=timezone.utc),
        resolved_at=datetime(2026, 8, 13, 0, 5, 0, tzinfo=timezone.utc),
        incident_id="INC-20260813-000001",
    )

    assert alert.resolved_at is not None
    assert alert.incident_id == "INC-20260813-000001"
