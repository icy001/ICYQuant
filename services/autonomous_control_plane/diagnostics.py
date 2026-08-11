"""
Control Plane Diagnostics — System diagnostics and troubleshooting.

Provides introspection and debugging capabilities for the Control Plane
and all its sub-engines.
"""

from __future__ import annotations

import time
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


class Diagnostics:
    """
    Diagnostics tool for the Control Plane.

    Provides introspection into engine states, decision pipelines,
    policy configurations, and recent activities.
    """

    def __init__(self):
        self._diag_checks: list[dict] = []

    def run_diagnostics(self, control_plane) -> dict:
        """Run a comprehensive diagnostic check on the Control Plane."""
        results = {}
        timestamp = time.time()

        # Check each engine
        engines = {
            "policy_engine": control_plane.policy_engine,
            "autonomy_engine": control_plane.autonomy_engine,
            "decision_engine": control_plane.decision_engine,
            "budget_manager": control_plane.budget_manager,
            "lifecycle_engine": control_plane.lifecycle_engine,
            "promotion_engine": control_plane.promotion_engine,
            "approval_engine": control_plane.approval_engine,
            "permission_engine": control_plane.permission_engine,
            "audit_engine": control_plane.audit_engine,
            "incident_manager": control_plane.incident_manager,
            "health_monitor": control_plane.health_monitor,
            "safety_layer": control_plane.safety_layer,
        }

        for name, instance in engines.items():
            if instance:
                results[name] = {
                    "status": "present",
                    "stats": instance.stats() if hasattr(instance, "stats") else {},
                }
            else:
                results[name] = {"status": "missing"}

        # Overall status
        issues = sum(
            1 for r in results.values()
            if r.get("status") == "missing"
        )
        results["overall"] = "healthy" if issues == 0 else f"{issues} issues"

        self._diag_checks.append({
            "timestamp": timestamp,
            "results": results,
        })

        return results

    def stats(self) -> dict:
        return {"checks_run": len(self._diag_checks)}
