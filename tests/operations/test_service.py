"""
Tests for service identity / state / health models
(Commit 27 Part 1.1, spec sections 4-7, 21).
"""

from datetime import datetime, timezone

from services.operations import (
    ServiceHealth,
    ServiceIdentity,
    ServiceState,
)


def test_service_state_members():
    """ServiceState exposes the six documented states."""
    assert {s.value for s in ServiceState} == {
        "STARTING",
        "HEALTHY",
        "DEGRADED",
        "UNHEALTHY",
        "STOPPED",
        "UNKNOWN",
    }


def test_service_state_values():
    assert ServiceState.HEALTHY.value == "HEALTHY"
    assert ServiceState.DEGRADED.value == "DEGRADED"
    assert ServiceState.UNHEALTHY.value == "UNHEALTHY"


def test_service_identity():
    """spec section 21: 生产环境必须能区分 service/instance/version/env。"""
    service = ServiceIdentity(
        service_id="risk-engine",
        name="Risk Engine",
        version="0.4.0-alpha2",
        environment="production",
        instance_id="risk-01",
    )

    assert service.service_id == "risk-engine"
    assert service.name == "Risk Engine"
    assert service.version == "0.4.0-alpha2"
    assert service.environment == "production"
    assert service.instance_id == "risk-01"


def test_service_identity_equality():
    a = ServiceIdentity(
        service_id="risk-engine",
        name="Risk Engine",
        version="0.4.0-alpha2",
        environment="production",
        instance_id="risk-02",
    )
    b = ServiceIdentity(
        service_id="risk-engine",
        name="Risk Engine",
        version="0.4.0-alpha2",
        environment="production",
        instance_id="risk-02",
    )

    assert a == b


def test_service_health_defaults():
    health = ServiceHealth(
        service_id="risk-engine",
        state=ServiceState.HEALTHY,
        checked_at=datetime.now(timezone.utc),
    )

    assert health.healthy
    assert health.latency_ms is None
    assert health.message == ""


def test_service_health_fields():
    health = ServiceHealth(
        service_id="risk-engine",
        state=ServiceState.DEGRADED,
        checked_at=datetime.now(timezone.utc),
        latency_ms=800.0,
        message="latency above threshold",
        healthy=False,
    )

    assert not health.healthy
    assert health.latency_ms == 800.0
    assert health.message == "latency above threshold"
    assert health.state is ServiceState.DEGRADED


def test_degraded_is_not_unhealthy():
    """spec section 7：DEGRADED != UNHEALTHY。

    Latency = 800ms 可能只是 DEGRADED，Heartbeat lost 才是 UNHEALTHY。
    """
    degraded = ServiceHealth(
        service_id="execution",
        state=ServiceState.DEGRADED,
        checked_at=datetime.now(timezone.utc),
        latency_ms=800.0,
        healthy=True,
    )
    unhealthy = ServiceHealth(
        service_id="execution",
        state=ServiceState.UNHEALTHY,
        checked_at=datetime.now(timezone.utc),
        latency_ms=None,
        healthy=False,
    )

    assert degraded.state is not unhealthy.state
    assert degraded.state is ServiceState.DEGRADED
    assert unhealthy.state is ServiceState.UNHEALTHY
