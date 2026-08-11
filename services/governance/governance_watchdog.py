"""
Governance Watchdog — monitors the control plane itself.

Part 1.5: the watchdog monitors governance components (control plane,
guardians, controllers) for health, ensuring the governance system
itself does not fail silently.

Principle: critical governance failure → FAIL CLOSED (default BLOCK).
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Dict, List, Optional

from .governance_heartbeat import GovernanceHeartbeat
from .governance_health import GovernanceHealth
from .control_trigger import ControlTrigger, TriggerType, Severity
from .control_state import GovernanceStateType


class GovernanceWatchdog:
    """Monitors governance system health and raises alerts.

    The watchdog checks:
      - Control plane health
      - Guardian health (risk, authority, approval, policy, execution)
      - Controller health (freeze, exposure, revoke, escalation, emergency)
      - Audit engine health
    """

    def __init__(self):
        self._health = GovernanceHealth()
        self._heartbeats: Dict[str, List[GovernanceHeartbeat]] = {}
        self._last_check: float = 0.0

        # Tracked components
        self._tracked_components: List[str] = [
            "control-plane",
            "risk-guardian",
            "authority-guardian",
            "approval-guardian",
            "policy-guardian",
            "execution-guardian",
            "freeze-controller",
            "exposure-controller",
            "revoke-controller",
            "escalation-controller",
            "emergency-controller",
            "policy-engine",
            "audit-engine",
        ]

        # Alert history
        self._alerts: List[Dict[str, Any]] = []

    def receive_heartbeat(self, heartbeat: GovernanceHeartbeat) -> None:
        """Receive and track a heartbeat from a governance component."""
        if heartbeat.component not in self._heartbeats:
            self._heartbeats[heartbeat.component] = []
        self._heartbeats[heartbeat.component].append(heartbeat)

        # Keep only recent
        max_hb = 100
        if len(self._heartbeats[heartbeat.component]) > max_hb:
            self._heartbeats[heartbeat.component] = self._heartbeats[heartbeat.component][-max_hb:]

        # Update health
        self._health.update_heartbeat(heartbeat)

    def check(self) -> Dict[str, Any]:
        """Run a watchdog health check.

        Returns:
            Dict with health status and any alerts.
        """
        self._last_check = time.time()
        health = self._health.assess()

        # Check for missing components
        for component in self._tracked_components:
            if component not in self._health.components:
                self._health.components[component] = {
                    "status": "UNKNOWN",
                    "last_beat": 0.0,
                    "age_seconds": float("inf"),
                    "version": "",
                    "uptime_seconds": 0.0,
                    "message": "No heartbeat received.",
                }

        # Generate alerts if unhealthy
        alerts: List[Dict[str, Any]] = []
        if self._health.overall_status != "HEALTHY":
            for issue in health.get("issues", []):
                alert = {
                    "alert_id": f"ALERT-{uuid.uuid4().hex[:12].upper()}",
                    "timestamp": time.time(),
                    "issue": issue,
                    "overall_status": self._health.overall_status,
                }
                alerts.append(alert)
                self._alerts.append(alert)

        return {
            "status": self._health.overall_status,
            "health": health,
            "alerts": alerts,
            "tracked_components": len(self._tracked_components),
            "healthy_components": sum(
                1 for c in self._health.components.values()
                if c.get("status") == "HEALTHY"
            ),
        }

    def get_fail_closed_decision(self) -> Dict[str, Any]:
        """Determine if governance should fail closed.

        If critical components are unhealthy, new risk should be BLOCKED.
        """
        health = self.check()

        critical_unhealthy = any(
            comp in self._health.critical_components and
            self._health.components.get(comp, {}).get("status") in ("UNHEALTHY", "STALE", "UNKNOWN")
            for comp in self._health.critical_components
        )

        return {
            "should_fail_closed": critical_unhealthy,
            "new_risk_allowed": not critical_unhealthy,
            "risk_reduction_allowed": True,  # Always allowed
            "reason": "Critical governance component(s) unhealthy" if critical_unhealthy else "All critical components healthy",
            "status": self._health.overall_status,
        }

    def get_alerts(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent watchdog alerts."""
        return list(reversed(self._alerts[-limit:]))

    def get_metrics(self) -> Dict[str, Any]:
        return {
            "overall_status": self._health.overall_status,
            "tracked_components": len(self._tracked_components),
            "components_healthy": sum(
                1 for c in self._health.components.values()
                if c.get("status") == "HEALTHY"
            ),
            "components_degraded": sum(
                1 for c in self._health.components.values()
                if c.get("status") == "DEGRADED"
            ),
            "components_unhealthy": sum(
                1 for c in self._health.components.values()
                if c.get("status") in ("UNHEALTHY", "STALE", "UNKNOWN")
            ),
            "alerts_count": len(self._alerts),
            "fail_closed": self.get_fail_closed_decision(),
        }
