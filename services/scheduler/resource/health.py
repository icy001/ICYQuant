"""Resource Health — aggregated health checks for the resource subsystem."""

from typing import Any, Dict, Optional


class ResourceHealth:
    """Aggregated health checker for the resource scheduling subsystem."""

    def check(
        self, manager: Any = None, pool: Any = None,
        tracker: Any = None, quota: Any = None,
        auto_scaler: Any = None, io_scheduler: Any = None,
    ) -> Dict[str, Any]:
        components: Dict[str, Any] = {}
        issues: list = []

        # Manager
        mgr_state = getattr(manager, "_state", "unknown") if manager else "n/a"
        components["manager"] = {"state": mgr_state}

        # Pool
        if pool:
            util = pool.utilization()
            components["pool"] = {
                "cpu_pct": round(util["cpu_pct"], 1),
                "memory_pct": round(util["memory_pct"], 1),
                "node_count": util["node_count"],
            }
            if util["cpu_pct"] > 90:
                issues.append(f"CPU critical: {util['cpu_pct']:.0f}%")
            elif util["cpu_pct"] > 80:
                issues.append(f"CPU warning: {util['cpu_pct']:.0f}%")

        # Tracker
        if tracker:
            components["tracker"] = {
                "active_allocations": tracker.count(),
            }

        # Quota
        if quota:
            components["quota"] = {"tenants": len(quota.list_quotas())}

        # Auto-scaler
        if auto_scaler:
            components["auto_scaler"] = auto_scaler.health_report()

        # IO
        if io_scheduler:
            components["io"] = {"hot_nodes": len(io_scheduler.get_hot_nodes())}

        overall = "critical" if any("critical" in str(i).lower() for i in issues) else (
            "degraded" if issues else "healthy"
        )

        return {
            "status": overall,
            "components": components,
            "issues": issues,
            "issue_count": len(issues),
        }

    def health_report(self) -> Dict[str, Any]:
        return {"status": "ready"}
