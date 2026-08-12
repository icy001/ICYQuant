"""Unit tests: HeartbeatMonitor — timeout, warning, critical, grace period."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from services.control_plane.health.heartbeat import Heartbeat
from services.control_plane.monitors.heartbeat_monitor import (
    HeartbeatDecision,
    HeartbeatMonitor,
)

NOW = datetime(2026, 8, 12, 10, 0, 0, tzinfo=timezone.utc)

MONITOR = HeartbeatMonitor(
    warning_timeout=10.0,
    critical_timeout=15.0,
    startup_grace_period=30.0,
    failure_threshold=3,
)


def hb_at(age_seconds: float, sequence: int = 100):
    return Heartbeat(
        component_id="risk_engine",
        instance_id="risk-01",
        sequence=sequence,
        timestamp=NOW - timedelta(seconds=age_seconds),
    )


class TestHeartbeatTimeout:
    def test_fresh_heartbeat_is_healthy(self):
        decision = MONITOR.evaluate(hb_at(age_seconds=2), now=NOW)
        assert decision.decision is HeartbeatDecision.HEALTHY
        assert decision.missed is False
        assert decision.elapsed == 2.0

    def test_warning_timeout_degraded(self):
        decision = MONITOR.evaluate(hb_at(age_seconds=12), now=NOW)
        assert decision.decision is HeartbeatDecision.DEGRADED
        assert decision.missed is True
        assert decision.reason == "WARNING_TIMEOUT"

    def test_critical_timeout_unhealthy(self):
        decision = MONITOR.evaluate(hb_at(age_seconds=20), now=NOW)
        assert decision.decision is HeartbeatDecision.UNHEALTHY
        assert decision.missed is True
        assert decision.reason == "CRITICAL_TIMEOUT"

    def test_boundary_warning_is_still_healthy(self):
        decision = MONITOR.evaluate(hb_at(age_seconds=10), now=NOW)
        assert decision.decision is HeartbeatDecision.HEALTHY

    def test_boundary_critical_is_degraded(self):
        decision = MONITOR.evaluate(hb_at(age_seconds=15), now=NOW)
        assert decision.decision is HeartbeatDecision.DEGRADED

    def test_metadata_carried(self):
        decision = MONITOR.evaluate(hb_at(age_seconds=2, sequence=10231), now=NOW)
        assert decision.last_sequence == 10231
        assert decision.component_id == "risk_engine"
        assert decision.instance_id == "risk-01"


class TestUnresponsive:
    def test_unresponsive_after_threshold(self):
        decision = MONITOR.evaluate(hb_at(age_seconds=20), now=NOW, miss_count=3)
        assert decision.decision is HeartbeatDecision.UNRESPONSIVE

    def test_not_unresponsive_before_threshold(self):
        decision = MONITOR.evaluate(hb_at(age_seconds=20), now=NOW, miss_count=2)
        assert decision.decision is HeartbeatDecision.UNHEALTHY


class TestStartupGracePeriod:
    def test_no_heartbeat_within_grace_is_starting(self):
        decision = MONITOR.evaluate(
            None,
            now=NOW,
            started_at=NOW - timedelta(seconds=10),
        )
        assert decision.decision is HeartbeatDecision.STARTING
        assert decision.missed is False

    def test_no_heartbeat_after_grace_is_unhealthy(self):
        decision = MONITOR.evaluate(
            None,
            now=NOW,
            started_at=NOW - timedelta(seconds=60),
        )
        assert decision.decision is HeartbeatDecision.UNHEALTHY
        assert decision.missed is True
        assert decision.reason == "NO_HEARTBEAT"

    def test_no_started_at_no_grace(self):
        decision = MONITOR.evaluate(None, now=NOW)
        assert decision.decision is HeartbeatDecision.UNHEALTHY
