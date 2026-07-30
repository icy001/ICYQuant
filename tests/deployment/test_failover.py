"""
Tests for ICYQuant Failover Manager.
"""

import pytest

from infrastructure.runtime.failover import (
    FailoverManager,
    FailoverState,
    HealthStatus,
    FailoverTarget,
    ServiceHealth,
)


class TestFailoverManager:
    """Test automated failover capabilities."""

    def test_register_service(self):
        fm = FailoverManager()
        targets = [
            FailoverTarget(service_id="api", cluster="primary", priority=1),
            FailoverTarget(service_id="api", cluster="standby", priority=2),
        ]
        fm.register_service("api", targets)
        status = fm.get_service_status("api")
        assert status["serviceId"] == "api"
        assert len(status["targets"]) == 2

    def test_update_health(self):
        fm = FailoverManager()
        fm.register_service("api", [
            FailoverTarget(service_id="api", cluster="primary"),
        ])
        fm.update_health("api", "primary", HealthStatus.HEALTHY, response_time_ms=50)
        status = fm.get_service_status("api")
        assert status["health"][0]["status"] == "HEALTHY"

    def test_manual_failover(self):
        fm = FailoverManager()
        fm.register_service("api", [
            FailoverTarget(service_id="api", cluster="primary", priority=1, active=True),
            FailoverTarget(service_id="api", cluster="standby", priority=2),
        ])
        event = fm.trigger_failover("api", target_cluster="standby", reason="manual")
        assert event.state == FailoverState.FAILOVER_COMPLETED
        assert event.from_cluster == "primary"
        assert event.to_cluster == "standby"

    def test_automatic_failover_on_health_failure(self):
        fm = FailoverManager()
        targets = [
            FailoverTarget(service_id="api", cluster="primary", priority=1, active=True),
            FailoverTarget(service_id="api", cluster="standby", priority=2),
        ]
        fm.register_service("api", targets)
        fm.update_health("api", "primary", HealthStatus.UNHEALTHY)
        fm.update_health("api", "standby", HealthStatus.HEALTHY)
        fm.update_health("api", "primary", HealthStatus.UNHEALTHY)
        fm.update_health("api", "primary", HealthStatus.UNHEALTHY)
        status = fm.get_service_status("api")
        assert status["state"] in (
            FailoverState.FAILOVER_COMPLETED.value,
            FailoverState.DEGRADED.value,
        )

    def test_rollback(self):
        fm = FailoverManager()
        fm.register_service("api", [
            FailoverTarget(service_id="api", cluster="primary", priority=1, active=True),
            FailoverTarget(service_id="api", cluster="standby", priority=2),
        ])
        fm.trigger_failover("api", target_cluster="standby")
        event = fm.rollback("api")
        assert event.state == FailoverState.ROLLBACK

    def test_multiple_services(self):
        fm = FailoverManager()
        fm.register_service("api", [
            FailoverTarget(service_id="api", cluster="primary"),
        ])
        fm.register_service("ai", [
            FailoverTarget(service_id="ai", cluster="primary"),
        ])
        status = fm.get_status()
        assert len(status["services"]) == 2

    def test_get_status(self):
        fm = FailoverManager()
        fm.register_service("api", [
            FailoverTarget(service_id="api", cluster="primary"),
        ])
        status = fm.get_status()
        assert "states" in status
        assert "recentEvents" in status

    def test_state_change_callback(self):
        fm = FailoverManager()
        callbacks = []
        fm.on_state_change(lambda svc, state: callbacks.append((svc, state)))
        fm.register_service("api", [
            FailoverTarget(service_id="api", cluster="primary"),
        ])
        fm.update_health("api", "primary", HealthStatus.UNHEALTHY)
        assert len(callbacks) > 0

    def test_failover_nonexistent_service(self):
        fm = FailoverManager()
        result = fm.trigger_failover("nonexistent", target_cluster="standby")
        assert result is None