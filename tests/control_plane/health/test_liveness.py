"""Unit tests: Liveness evaluation (ALIVE / DEAD / UNKNOWN)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from services.control_plane.health.heartbeat import Heartbeat
from services.control_plane.health.liveness import (
    FunctionLivenessProbe,
    HeartbeatLivenessProbe,
    LivenessStatus,
    StaticLivenessProbe,
)
from services.control_plane.monitors.liveness_monitor import LivenessMonitor

NOW = datetime(2026, 8, 12, 10, 0, 0, tzinfo=timezone.utc)


def hb_at(age_seconds: float):
    return Heartbeat(
        component_id="risk_engine",
        instance_id="risk-01",
        sequence=1,
        timestamp=NOW - timedelta(seconds=age_seconds),
    )


class TestLivenessStatus:
    def test_values(self):
        assert [s.value for s in LivenessStatus] == ["ALIVE", "DEAD", "UNKNOWN"]

    def test_is_alive(self):
        assert LivenessStatus.ALIVE.is_alive
        assert not LivenessStatus.DEAD.is_alive


class TestHeartbeatLivenessProbe:
    def test_alive_within_timeout(self):
        probe = HeartbeatLivenessProbe(
            last_heartbeat=lambda cid: hb_at(age_seconds=3), timeout=5.0
        )
        assert probe.check("risk_engine", now=NOW) is LivenessStatus.ALIVE

    def test_dead_beyond_timeout(self):
        probe = HeartbeatLivenessProbe(
            last_heartbeat=lambda cid: hb_at(age_seconds=8), timeout=5.0
        )
        assert probe.check("risk_engine", now=NOW) is LivenessStatus.DEAD

    def test_unknown_without_heartbeat(self):
        probe = HeartbeatLivenessProbe(last_heartbeat=lambda cid: None)
        assert probe.check("risk_engine", now=NOW) is LivenessStatus.UNKNOWN


class TestStaticLivenessProbe:
    def test_mapping_lookup(self):
        probe = StaticLivenessProbe({"execution_engine": LivenessStatus.ALIVE})
        assert probe.check("execution_engine") is LivenessStatus.ALIVE
        assert probe.check("unknown_service") is LivenessStatus.UNKNOWN


class TestFunctionLivenessProbe:
    def test_wraps_callable(self):
        probe = FunctionLivenessProbe(lambda cid: LivenessStatus.DEAD)
        assert probe.check("any") is LivenessStatus.DEAD


class TestLivenessMonitor:
    def test_check_returns_evaluation(self):
        monitor = LivenessMonitor(probe=StaticLivenessProbe({"risk": LivenessStatus.ALIVE}))
        evaluation = monitor.check("risk", now=NOW)
        assert evaluation.component_id == "risk"
        assert evaluation.status is LivenessStatus.ALIVE
        assert evaluation.evaluated_at == NOW

    def test_evaluation_serializes(self):
        monitor = LivenessMonitor(probe=StaticLivenessProbe({}))
        evaluation = monitor.check("risk", now=NOW)
        data = evaluation.to_dict()
        assert data["status"] == "UNKNOWN"
        assert data["component_id"] == "risk"
