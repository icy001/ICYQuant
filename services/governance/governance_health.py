"""
Governance Health — governance system health assessment.

Part 1.5: holistic health assessment of the entire governance subsystem,
aggregating component heartbeats into an overall health status.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .governance_heartbeat import GovernanceHeartbeat


@dataclass
class GovernanceHealth:
    """Holistic health assessment of the governance system."""

    overall_status: str = "HEALTHY"  # HEALTHY / DEGRADED / UNHEALTHY
    components: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    issues: List[str] = field(default_factory=list)
    last_assessment: float = field(default_factory=time.time)

    # Configuration
    heartbeat_timeout_seconds: float = 60.0
    critical_components: List[str] = field(default_factory=lambda: [
        "control-plane",
        "policy-engine",
        "audit-engine",
    ])

    def update_heartbeat(self, heartbeat: GovernanceHeartbeat) -> None:
        """Update component health from a heartbeat."""
        self.components[heartbeat.component] = {
            "status": heartbeat.status,
            "last_beat": heartbeat.sent_at,
            "age_seconds": heartbeat.age_seconds,
            "version": heartbeat.version,
            "uptime_seconds": heartbeat.uptime_seconds,
            "message": heartbeat.message,
        }

    def assess(self) -> Dict[str, Any]:
        """Run a full health assessment.

        Returns:
            Dict with overall status and per-component health.
        """
        self.last_assessment = time.time()
        self.issues.clear()

        component_statuses = []

        for component, info in self.components.items():
            age = time.time() - info["last_beat"]

            # Check for stale heartbeats
            if age > self.heartbeat_timeout_seconds:
                status = "STALE"
                self.issues.append(f"{component} heartbeat stale ({age:.0f}s)")
            elif info["status"] == "UNHEALTHY":
                status = "UNHEALTHY"
                self.issues.append(f"{component} is unhealthy: {info.get('message', '')}")
            elif info["status"] == "DEGRADED":
                status = "DEGRADED"
            else:
                status = "HEALTHY"

            component_statuses.append(status)

            # Critical component failure
            if component in self.critical_components and status in ("UNHEALTHY", "STALE"):
                self.issues.insert(0, f"CRITICAL: {component} is {status}")

        # Determine overall status
        if any(c in ("UNHEALTHY", "STALE") for c in component_statuses):
            # Check if any critical component is unhealthy
            critical_failure = any(
                comp in self.critical_components and
                self.components.get(comp, {}).get("status") != "HEALTHY"
                for comp in self.critical_components
            )
            if critical_failure:
                self.overall_status = "UNHEALTHY"
            else:
                self.overall_status = "DEGRADED"
        elif "DEGRADED" in component_statuses:
            self.overall_status = "DEGRADED"
        else:
            self.overall_status = "HEALTHY"

        return {
            "overall_status": self.overall_status,
            "components": {
                comp: {
                    "status": info["status"],
                    "age_seconds": time.time() - info["last_beat"],
                }
                for comp, info in self.components.items()
            },
            "issues": self.issues,
            "assessed_at": self.last_assessment,
        }

    def is_healthy(self) -> bool:
        return self.overall_status == "HEALTHY"

    def is_degraded(self) -> bool:
        return self.overall_status == "DEGRADED"

    def is_unhealthy(self) -> bool:
        return self.overall_status == "UNHEALTHY"

    def to_dict(self) -> Dict[str, Any]:
        return self.assess()
