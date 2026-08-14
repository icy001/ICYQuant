"""Control Plane health tests (Commit 29 Part 1.5 §35-38, §60)."""

from __future__ import annotations

from services.control_plane.control_health import (
    ControlPlaneHealth,
    DependencyProbe,
    HealthStatus,
)


def test_liveness_is_independent_of_dependencies():
    health = ControlPlaneHealth(
        [DependencyProbe("command_store", lambda: HealthStatus.UNHEALTHY)]
    )
    assert health.liveness() == "ALIVE"


def test_not_ready_when_command_store_down():
    command_store = {"failed": False}

    def check_command_store():
        return HealthStatus.UNHEALTHY if command_store["failed"] else HealthStatus.HEALTHY

    health = ControlPlaneHealth(
        [
            DependencyProbe("command_store", check_command_store),
            DependencyProbe("authorization", lambda: HealthStatus.HEALTHY),
        ]
    )
    assert health.readiness() == "READY"
    command_store["failed"] = True
    assert health.readiness() == "NOT_READY"


def test_snapshot_reports_dependency_health():
    health = ControlPlaneHealth(
        [
            DependencyProbe("command_store", lambda: HealthStatus.HEALTHY),
            DependencyProbe("event_sink", lambda: HealthStatus.DEGRADED),
            DependencyProbe("authorization", lambda: HealthStatus.UNHEALTHY),
        ]
    )
    snapshot = health.snapshot()
    assert snapshot.liveness == "ALIVE"
    assert snapshot.overall is HealthStatus.UNHEALTHY
    names = [dependency.name for dependency in snapshot.dependencies]
    assert names == ["command_store", "event_sink", "authorization"]


def test_degraded_overall_when_only_non_critical_down():
    health = ControlPlaneHealth(
        [
            DependencyProbe("command_store", lambda: HealthStatus.HEALTHY),
            DependencyProbe("event_sink", lambda: HealthStatus.DEGRADED, critical=False),
        ]
    )
    snapshot = health.snapshot()
    assert snapshot.overall is HealthStatus.DEGRADED
    # A degraded non-critical dependency does not block readiness.
    assert snapshot.readiness == "READY"


def test_register_probe_dynamically():
    health = ControlPlaneHealth()
    health.register(DependencyProbe("target_registry", lambda: HealthStatus.HEALTHY))
    assert health.readiness() == "READY"
    assert len(health.snapshot().dependencies) == 1
