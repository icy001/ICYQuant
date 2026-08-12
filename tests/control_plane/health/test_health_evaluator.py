"""Unit tests: Health evaluation matrix, health score, criticality,
active checks, passive heartbeat."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from services.control_plane.domain.component_registry import ComponentCriticality
from services.control_plane.health.health_check import (
    HealthCheck,
    HealthCheckResult,
    run_health_check,
)
from services.control_plane.health.health_evaluator import HealthEvaluator
from services.control_plane.health.health_status import HealthStatus
from services.control_plane.health.heartbeat import Heartbeat
from services.control_plane.health.liveness import LivenessStatus
from services.control_plane.health.readiness import (
    DependencyStatus,
    ReadinessStatus,
)

NOW = datetime(2026, 8, 12, 10, 0, 0, tzinfo=timezone.utc)

EVALUATOR = HealthEvaluator()


def dep(component_id, status=HealthStatus.HEALTHY):
    return DependencyStatus(component_id=component_id, status=status)


def hb_at(age_seconds: float, status=None):
    return Heartbeat(
        component_id="risk_engine",
        instance_id="risk-01",
        sequence=1,
        timestamp=NOW - timedelta(seconds=age_seconds),
    )


class TestStateMatrix:
    def test_alive_ready_healthy(self):
        e = EVALUATOR.evaluate(
            "risk_engine",
            liveness=LivenessStatus.ALIVE,
            readiness=ReadinessStatus.READY,
            now=NOW,
        )
        assert e.status is HealthStatus.HEALTHY

    def test_alive_not_ready_degraded(self):
        e = EVALUATOR.evaluate(
            "risk_engine",
            liveness=LivenessStatus.ALIVE,
            readiness=ReadinessStatus.NOT_READY,
            now=NOW,
        )
        assert e.status is HealthStatus.DEGRADED

    def test_alive_failed_unhealthy(self):
        e = EVALUATOR.evaluate(
            "risk_engine",
            liveness=LivenessStatus.ALIVE,
            readiness=ReadinessStatus.FAILED,
            now=NOW,
        )
        assert e.status is HealthStatus.UNHEALTHY

    def test_dead_is_always_unhealthy(self):
        for readiness in ReadinessStatus:
            e = EVALUATOR.evaluate(
                "risk_engine",
                liveness=LivenessStatus.DEAD,
                readiness=readiness,
                now=NOW,
            )
            assert e.status is HealthStatus.UNHEALTHY

    def test_unknown_unknown_is_unknown(self):
        e = EVALUATOR.evaluate(
            "risk_engine",
            liveness=LivenessStatus.UNKNOWN,
            readiness=ReadinessStatus.UNKNOWN,
            now=NOW,
        )
        assert e.status is HealthStatus.UNKNOWN


class TestPassiveHeartbeat:
    def test_fresh_heartbeat_keeps_healthy(self):
        e = EVALUATOR.evaluate(
            "risk_engine",
            liveness=LivenessStatus.ALIVE,
            readiness=ReadinessStatus.READY,
            heartbeat=hb_at(age_seconds=2),
            heartbeat_age=2.0,
            now=NOW,
        )
        assert e.status is HealthStatus.HEALTHY

    def test_warning_timeout_degraded(self):
        e = EVALUATOR.evaluate(
            "risk_engine",
            liveness=LivenessStatus.ALIVE,
            readiness=ReadinessStatus.READY,
            heartbeat_age=12.0,
            warning_timeout=10.0,
            critical_timeout=15.0,
            now=NOW,
        )
        assert e.status is HealthStatus.DEGRADED
        assert "HEARTBEAT_WARNING_TIMEOUT" in e.reasons

    def test_critical_timeout_unhealthy(self):
        e = EVALUATOR.evaluate(
            "risk_engine",
            liveness=LivenessStatus.ALIVE,
            readiness=ReadinessStatus.READY,
            heartbeat_age=20.0,
            warning_timeout=10.0,
            critical_timeout=15.0,
            now=NOW,
        )
        assert e.status is HealthStatus.UNHEALTHY
        assert "HEARTBEAT_CRITICAL_TIMEOUT" in e.reasons

    def test_heartbeat_status_degraded(self):
        e = EVALUATOR.evaluate(
            "risk_engine",
            liveness=LivenessStatus.ALIVE,
            readiness=ReadinessStatus.READY,
            heartbeat_status="DEGRADED",
            now=NOW,
        )
        assert e.status is HealthStatus.DEGRADED


class TestDependencyHealth:
    def test_unhealthy_dependency_degrades(self):
        e = EVALUATOR.evaluate(
            "risk_engine",
            liveness=LivenessStatus.ALIVE,
            readiness=ReadinessStatus.READY,
            dependencies=[dep("position", HealthStatus.UNHEALTHY)],
            now=NOW,
        )
        assert e.status is HealthStatus.DEGRADED
        assert "DEPENDENCY_UNHEALTHY" in e.reasons

    def test_degraded_dependency_degrades(self):
        e = EVALUATOR.evaluate(
            "risk_engine",
            liveness=LivenessStatus.ALIVE,
            readiness=ReadinessStatus.READY,
            dependencies=[dep("event_bus", HealthStatus.DEGRADED)],
            now=NOW,
        )
        assert e.status is HealthStatus.DEGRADED

    def test_healthy_dependencies_keep_healthy(self):
        e = EVALUATOR.evaluate(
            "risk_engine",
            liveness=LivenessStatus.ALIVE,
            readiness=ReadinessStatus.READY,
            dependencies=[dep("position"), dep("event_bus")],
            now=NOW,
        )
        assert e.status is HealthStatus.HEALTHY


class TestActiveHealthCheck:
    def test_fail_overrides_to_unhealthy(self):
        e = EVALUATOR.evaluate(
            "risk_engine",
            liveness=LivenessStatus.ALIVE,
            readiness=ReadinessStatus.READY,
            checks=[HealthCheck("db", "risk_engine", HealthCheckResult.FAIL)],
            now=NOW,
        )
        assert e.status is HealthStatus.UNHEALTHY
        assert "HEALTH_CHECK_FAIL" in e.reasons

    def test_warn_overrides_to_degraded(self):
        e = EVALUATOR.evaluate(
            "risk_engine",
            liveness=LivenessStatus.ALIVE,
            readiness=ReadinessStatus.READY,
            checks=[HealthCheck("db", "risk_engine", HealthCheckResult.WARN)],
            now=NOW,
        )
        assert e.status is HealthStatus.DEGRADED
        assert "HEALTH_CHECK_WARN" in e.reasons

    def test_pass_keeps_healthy(self):
        e = EVALUATOR.evaluate(
            "risk_engine",
            liveness=LivenessStatus.ALIVE,
            readiness=ReadinessStatus.READY,
            checks=[HealthCheck("db", "risk_engine", HealthCheckResult.PASS)],
            now=NOW,
        )
        assert e.status is HealthStatus.HEALTHY

    def test_run_health_check_probe(self):
        check = run_health_check(
            "db_query", "risk_engine", lambda cid: HealthCheckResult.PASS, now=NOW
        )
        assert check.result is HealthCheckResult.PASS
        assert check.checked_at == NOW

    def test_run_health_check_exception_is_fail(self):
        def broken(_cid):
            raise RuntimeError("boom")

        check = run_health_check("db_query", "risk_engine", broken, now=NOW)
        assert check.result is HealthCheckResult.FAIL
        assert "boom" in check.detail


class TestHealthScore:
    def test_full_score(self):
        score = HealthEvaluator.score(
            heartbeat_age=2.0,
            liveness=LivenessStatus.ALIVE,
            readiness=ReadinessStatus.READY,
            dependencies=[dep("position")],
        )
        assert score == pytest.approx(100.0)

    def test_degraded_score_components(self):
        score = HealthEvaluator.score(
            heartbeat_age=12.0,
            liveness=LivenessStatus.ALIVE,
            readiness=ReadinessStatus.NOT_READY,
            dependencies=[dep("position", HealthStatus.UNHEALTHY)],
            warning_timeout=10.0,
            critical_timeout=15.0,
        )
        # heartbeat 76, liveness 100, readiness 60, dependencies 0
        expected = 0.30 * 76 + 0.25 * 100 + 0.25 * 60 + 0.20 * 0
        assert score == pytest.approx(expected)

    def test_dead_component_scores_zero(self):
        score = HealthEvaluator.score(
            liveness=LivenessStatus.DEAD,
            readiness=ReadinessStatus.READY,
        )
        assert score == pytest.approx(0.30 * 0 + 0.25 * 0 + 0.25 * 100 + 0.20 * 100)

    def test_evaluation_carries_score(self):
        e = EVALUATOR.evaluate(
            "risk_engine",
            liveness=LivenessStatus.ALIVE,
            readiness=ReadinessStatus.READY,
            heartbeat_age=2.0,
            dependencies=[dep("position")],
            now=NOW,
        )
        assert e.score == pytest.approx(100.0)


class TestCriticality:
    def test_criticality_is_carried(self):
        e = EVALUATOR.evaluate(
            "event_bus",
            liveness=LivenessStatus.ALIVE,
            readiness=ReadinessStatus.READY,
            criticality=ComponentCriticality.TRADING_CRITICAL,
            now=NOW,
        )
        assert e.criticality is ComponentCriticality.TRADING_CRITICAL

    def test_evaluation_serialization(self):
        e = EVALUATOR.evaluate(
            "position_service",
            liveness=LivenessStatus.ALIVE,
            readiness=ReadinessStatus.NOT_READY,
            criticality=ComponentCriticality.OPERATIONAL,
            now=NOW,
        )
        data = e.to_dict()
        assert data["status"] == "DEGRADED"
        assert data["criticality"] == "OPERATIONAL"
        assert data["readiness"] == "NOT_READY"
