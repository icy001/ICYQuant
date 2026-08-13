"""
Tests for ServiceHealthMonitor (Commit 27 Part 1.1, spec sections 12, 21).
"""

from services.operations import (
    ServiceHealthMonitor,
    ServiceState,
)


def test_health_update():
    """spec section 21: update 返回最新的健康记录。"""
    monitor = ServiceHealthMonitor()

    health = monitor.update(
        "risk-engine",
        ServiceState.HEALTHY,
        latency_ms=12.5,
    )

    assert health.healthy
    assert health.latency_ms == 12.5
    assert health.service_id == "risk-engine"
    assert health.state is ServiceState.HEALTHY
    assert health.checked_at is not None


def test_health_get_returns_updated_record():
    monitor = ServiceHealthMonitor()

    monitor.update("risk-engine", ServiceState.HEALTHY)

    health = monitor.get("risk-engine")

    assert health is not None
    assert health.service_id == "risk-engine"
    assert health.state is ServiceState.HEALTHY


def test_health_get_unknown_service_returns_none():
    monitor = ServiceHealthMonitor()

    assert monitor.get("not-registered") is None


def test_health_update_overwrites_previous_state():
    monitor = ServiceHealthMonitor()

    monitor.update(
        "execution",
        ServiceState.HEALTHY,
        latency_ms=10.0,
    )
    monitor.update(
        "execution",
        ServiceState.DEGRADED,
        latency_ms=900.0,
        message="latency above threshold",
        healthy=False,
    )

    health = monitor.get("execution")

    assert health.state is ServiceState.DEGRADED
    assert health.latency_ms == 900.0
    assert not health.healthy
    assert health.message == "latency above threshold"


def test_health_tracks_multiple_services():
    monitor = ServiceHealthMonitor()

    monitor.update("risk-engine", ServiceState.HEALTHY)
    monitor.update("event-bus", ServiceState.UNHEALTHY)

    assert monitor.get("risk-engine").state is ServiceState.HEALTHY
    assert monitor.get("event-bus").state is ServiceState.UNHEALTHY
