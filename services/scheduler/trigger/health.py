"""Trigger Health — aggregated health checks for the trigger subsystem.

The :class:`TriggerHealth` aggregates health reports from the engine,
manager, queue, misfire handler, and dispatcher into a single status
object suitable for monitoring dashboards and alerting.
"""

from __future__ import annotations

from typing import Any, Dict, Optional


class TriggerHealth:
    """Aggregated health checker for the trigger subsystem.

    Usage::

        health = TriggerHealth()
        status = health.check(engine, manager, queue, misfire_handler, dispatcher)
    """

    # Healthy thresholds
    QUEUE_WARN_THRESHOLD_PCT = 70
    QUEUE_CRITICAL_THRESHOLD_PCT = 90
    MISFIRE_WARN_THRESHOLD = 10

    def check(
        self,
        engine: Any,
        manager: Any,
        queue: Any,
        misfire_handler: Any,
        dispatcher: Any,
    ) -> Dict[str, Any]:
        """Run a full health check and return a status dict."""
        components: Dict[str, Any] = {}
        issues: list = []

        # Engine
        engine_status = getattr(engine, "_state", "unknown")
        components["engine"] = {"state": engine_status}
        if engine_status in ("error", "stopped"):
            issues.append(f"Trigger engine is {engine_status}")

        # Manager
        total = getattr(manager, "get_trigger_count", lambda: 0)()
        enabled = 0
        for t in getattr(manager, "list_triggers", lambda: [])():
            if t.get("enabled"):
                enabled += 1
        components["manager"] = {
            "total_triggers": total,
            "enabled": enabled,
            "disabled": total - enabled,
        }

        # Queue
        depth = len(queue) if hasattr(queue, "__len__") else 0
        max_size = getattr(queue, "_max_size", 100_000)
        utilization = depth / max(max_size, 1) * 100
        queue_status = "healthy"
        if utilization > self.QUEUE_CRITICAL_THRESHOLD_PCT:
            queue_status = "critical"
            issues.append(f"Queue utilization is critical at {utilization:.1f}%")
        elif utilization > self.QUEUE_WARN_THRESHOLD_PCT:
            queue_status = "warning"
            issues.append(f"Queue utilization is high at {utilization:.1f}%")
        components["queue"] = {
            "depth": depth,
            "max_size": max_size,
            "utilization_pct": round(utilization, 2),
            "status": queue_status,
        }

        # Misfire handler
        if misfire_handler:
            mf_report = getattr(misfire_handler, "health_report", lambda: {})()
            components["misfire"] = mf_report
            total_misfires = mf_report.get("total_misfires", 0)
            if total_misfires > self.MISFIRE_WARN_THRESHOLD:
                issues.append(f"Misfire count is elevated: {total_misfires}")

        # Dispatcher
        if dispatcher:
            components["dispatcher"] = getattr(dispatcher, "health_report", lambda: {})()

        # Overall status
        overall = "healthy"
        if any("critical" in str(i).lower() for i in issues):
            overall = "critical"
        elif issues:
            overall = "degraded"

        return {
            "status": overall,
            "components": components,
            "issues": issues,
            "issue_count": len(issues),
        }

    def quick_check(self, engine: Any, queue: Any) -> Dict[str, Any]:
        """Fast health check (engine state + queue depth only)."""
        state = getattr(engine, "_state", "unknown")
        depth = len(queue) if hasattr(queue, "__len__") else 0
        return {
            "engine_state": state,
            "queue_depth": depth,
            "healthy": state in ("running", "ready") and depth < 100_000,
        }

    def health_report(self) -> Dict[str, Any]:
        return {"status": "ready"}
