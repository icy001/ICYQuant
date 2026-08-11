"""Test Watchdog — governance health monitoring."""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
import pytest

from services.governance.governance_heartbeat import GovernanceHeartbeat
from services.governance.governance_health import GovernanceHealth
from services.governance.governance_watchdog import GovernanceWatchdog


class TestGovernanceHeartbeat:
    """Test heartbeat signals."""

    def test_healthy_heartbeat(self):
        hb = GovernanceHeartbeat.healthy("test-component", version="1.0")
        assert hb.status == "HEALTHY"
        assert hb.is_healthy
        assert not hb.is_degraded

    def test_degraded_heartbeat(self):
        hb = GovernanceHeartbeat.degraded("test-component", "Slow response.")
        assert hb.is_degraded
        assert not hb.is_healthy

    def test_unhealthy_heartbeat(self):
        hb = GovernanceHeartbeat.unhealthy("test-component", "Service down.")
        assert hb.is_unhealthy

    def test_age_seconds(self):
        hb = GovernanceHeartbeat.healthy("test")
        assert hb.age_seconds >= 0


class TestGovernanceHealth:
    """Test governance health assessment."""

    def test_initial_health(self):
        gh = GovernanceHealth()
        assert gh.overall_status == "HEALTHY"

    def test_update_heartbeat(self):
        gh = GovernanceHealth()
        hb = GovernanceHeartbeat.healthy("control-plane")
        gh.update_heartbeat(hb)
        assert "control-plane" in gh.components

    def test_all_healthy(self):
        gh = GovernanceHealth()
        for comp in ["control-plane", "risk-guardian", "policy-engine"]:
            gh.update_heartbeat(GovernanceHeartbeat.healthy(comp))
        result = gh.assess()
        assert result["overall_status"] == "HEALTHY"

    def test_degraded_component(self):
        gh = GovernanceHealth()
        gh.update_heartbeat(GovernanceHeartbeat.healthy("control-plane"))
        gh.update_heartbeat(GovernanceHeartbeat.degraded("risk-guardian", "Slow"))
        result = gh.assess()
        assert result["overall_status"] in ("HEALTHY", "DEGRADED")

    def test_critical_component_unhealthy(self):
        gh = GovernanceHealth()
        gh.update_heartbeat(GovernanceHeartbeat.healthy("risk-guardian"))
        # control-plane is critical
        gh.components["control-plane"] = {
            "status": "UNHEALTHY",
            "last_beat": time.time(),
            "age_seconds": 5,
            "version": "",
            "uptime_seconds": 0,
            "message": "Down",
        }
        result = gh.assess()
        assert result["overall_status"] in ("DEGRADED", "UNHEALTHY")


class TestGovernanceWatchdog:
    """Test governance watchdog."""

    def test_initial_state(self):
        wd = GovernanceWatchdog()
        result = wd.check()
        assert "status" in result

    def test_receive_heartbeat(self):
        wd = GovernanceWatchdog()
        hb = GovernanceHeartbeat.healthy("control-plane")
        wd.receive_heartbeat(hb)
        assert "control-plane" in wd._health.components

    def test_fail_closed_decision(self):
        wd = GovernanceWatchdog()
        result = wd.get_fail_closed_decision()
        assert "should_fail_closed" in result
        # Initially all components are UNKNOWN, critical ones should fail closed
        assert result["risk_reduction_allowed"] is True  # Always allowed

    def test_metrics(self):
        wd = GovernanceWatchdog()
        metrics = wd.get_metrics()
        assert "overall_status" in metrics
        assert "tracked_components" in metrics
