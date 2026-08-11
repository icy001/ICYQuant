"""
Governance Health — lightweight health endpoint for the governance subsystem.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from .governance_manager import GovernanceManager


class GovernanceHealth:
    """
    Health indicator for the governance subsystem.
    Provides quick status checks for monitoring and alerting.
    """

    def __init__(self, manager: Optional[GovernanceManager] = None):
        self._manager = manager
        self._last_check: Dict[str, Any] = {}
        self._start_time = time.time()

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    @property
    def start_time(self) -> float:
        return self._start_time

    @property
    def uptime_seconds(self) -> float:
        return time.time() - self._start_time

    # ------------------------------------------------------------------
    # Health check
    # ------------------------------------------------------------------

    def is_healthy(self) -> bool:
        """Quick healthy/unhealthy check."""
        return self.check()["status"] == "HEALTHY"

    def check(self) -> Dict[str, Any]:
        """Run a health check and return status."""
        status = "HEALTHY"
        details: List[str] = []

        if self._manager:
            snapshot = self._manager.get_snapshot()

            # Check if running
            if not snapshot.get("started", False):
                status = "UNHEALTHY"
                details.append("Governance manager not started")

            # Check if enabled
            if not snapshot.get("enabled", True):
                status = "DEGRADED"
                details.append("Governance is disabled")

            # Check runtime stats
            runtime = snapshot.get("runtime", {})
            runtime_state = runtime.get("state", "UNKNOWN")
            if runtime_state not in ("RUNNING", "DEGRADED"):
                status = "DEGRADED"
                details.append(f"Runtime state: {runtime_state}")

            # Check error rate
            stats = runtime.get("stats", {})
            total = stats.get("total", 0)
            errors = stats.get("errors", 0)
            if total > 0 and errors / total > 0.1:
                status = "DEGRADED"
                details.append(f"High error rate: {errors}/{total}")
        else:
            status = "UNKNOWN"
            details.append("No manager connected")

        self._last_check = {
            "status": status,
            "uptime_seconds": self.uptime_seconds,
            "details": details,
            "timestamp": time.time(),
        }

        return self._last_check

    # ------------------------------------------------------------------
    # Readiness
    # ------------------------------------------------------------------

    def is_ready(self) -> bool:
        """Check if governance is ready to process decisions."""
        if not self._manager:
            return False
        snapshot = self._manager.get_snapshot()
        if not snapshot.get("started", False):
            return False
        if not snapshot.get("enabled", True):
            return False
        runtime = snapshot.get("runtime", {})
        return runtime.get("state", "") == "RUNNING"

    # ------------------------------------------------------------------
    # Metrics snapshot
    # ------------------------------------------------------------------

    def get_metrics_snapshot(self) -> Dict[str, Any]:
        """Get a quick metrics snapshot for monitoring."""
        if not self._manager:
            return {"error": "No manager"}

        snapshot = self._manager.get_snapshot()
        runtime = snapshot.get("runtime", {})
        stats = runtime.get("stats", {})

        return {
            "uptime_seconds": self.uptime_seconds,
            "total_decisions": stats.get("total", 0),
            "allowed": stats.get("allowed", 0),
            "rejected": stats.get("rejected", 0),
            "blocked": stats.get("blocked", 0),
            "errors": stats.get("errors", 0),
            "avg_latency_ms": stats.get("avg_latency_ms", 0),
            "policies_count": snapshot.get("policies_count", 0),
            "audit_records": snapshot.get("audit_records", 0),
            "events": snapshot.get("events", 0),
        }
