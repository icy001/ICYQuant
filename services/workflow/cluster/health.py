"""Cluster Health — aggregated health checking for all cluster components.

Returns a unified health report::

    {
        "cluster_manager": true,
        "coordinator": true,
        "leader_election": true,
        "heartbeat": true,
        "worker_registry": true,
        "failover": true,
        "recovery": true,
        "quorum": true
    }
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class ClusterHealthChecker:
    """Aggregates health status across all cluster components.

    Usage::

        checker = ClusterHealthChecker()
        report = await checker.check_all(cluster_manager, coordinator, ...)
    """

    def __init__(self) -> None:
        self._last_check: Optional[str] = None

    # ------------------------------------------------------------------
    # Component checks
    # ------------------------------------------------------------------

    async def check_cluster_manager(self, manager) -> Dict[str, Any]:
        try:
            report = manager.health_report()
            return {"healthy": True, "state": report.get("state"), "details": report}
        except Exception as e:
            return {"healthy": False, "error": str(e)}

    async def check_coordinator(self, coordinator) -> Dict[str, Any]:
        try:
            report = coordinator.health_report()
            return {"healthy": report.get("state") == "active", "details": report}
        except Exception as e:
            return {"healthy": False, "error": str(e)}

    async def check_leader_election(self, leader_election) -> Dict[str, Any]:
        try:
            report = leader_election.health_report()
            return {
                "healthy": report.get("state") != "stopped",
                "is_leader": report.get("is_leader"),
                "term": report.get("term"),
            }
        except Exception as e:
            return {"healthy": False, "error": str(e)}

    async def check_heartbeat(self, heartbeat_monitor) -> Dict[str, Any]:
        try:
            report = heartbeat_monitor.health_report()
            return {
                "healthy": True,
                "monitored": report.get("monitored_nodes", 0),
                "alive": report.get("alive_nodes", 0),
            }
        except Exception as e:
            return {"healthy": False, "error": str(e)}

    async def check_worker_registry(self, worker_registry) -> Dict[str, Any]:
        try:
            report = worker_registry.health_report()
            return {
                "healthy": True,
                "total": report.get("total_workers", 0),
                "available": report.get("available_workers", 0),
            }
        except Exception as e:
            return {"healthy": False, "error": str(e)}

    async def check_failover(self, failover_manager) -> Dict[str, Any]:
        try:
            report = failover_manager.health_report()
            return {
                "healthy": True,
                "tracked": report.get("tracked_executions", 0),
                "failovers": report.get("failover_count", 0),
            }
        except Exception as e:
            return {"healthy": False, "error": str(e)}

    async def check_recovery(self, recovery_coordinator) -> Dict[str, Any]:
        try:
            report = recovery_coordinator.health_report()
            return {
                "healthy": True,
                "active": report.get("active_recoveries", 0),
                "total": report.get("total_recoveries", 0),
                "success_rate": report.get("success_rate", 1.0),
            }
        except Exception as e:
            return {"healthy": False, "error": str(e)}

    async def check_quorum(self, quorum_manager) -> Dict[str, Any]:
        try:
            report = quorum_manager.health_report()
            return {
                "healthy": report.get("can_form_quorum", False),
                "active_nodes": report.get("active_nodes", 0),
                "required_votes": report.get("required_votes", 0),
            }
        except Exception as e:
            return {"healthy": False, "error": str(e)}

    async def check_shards(self, shard_manager) -> Dict[str, Any]:
        try:
            report = shard_manager.health_report()
            return {
                "healthy": True,
                "shard_count": report.get("shard_count", 0),
                "total_workflows": report.get("total_workflows", 0),
            }
        except Exception as e:
            return {"healthy": False, "error": str(e)}

    async def check_scheduler(self, scheduler) -> Dict[str, Any]:
        try:
            report = scheduler.health_report()
            return {
                "healthy": True,
                "queue_size": report.get("queue_size", 0),
            }
        except Exception as e:
            return {"healthy": False, "error": str(e)}

    # ------------------------------------------------------------------
    # Aggregate
    # ------------------------------------------------------------------

    async def check_all(
        self,
        *,
        cluster_manager=None,
        coordinator=None,
        leader_election=None,
        heartbeat_monitor=None,
        worker_registry=None,
        failover_manager=None,
        recovery_coordinator=None,
        quorum_manager=None,
        shard_manager=None,
        scheduler=None,
    ) -> Dict[str, Any]:
        """Run all health checks and return an aggregated report."""
        from datetime import datetime
        self._last_check = datetime.utcnow().isoformat()

        checks: Dict[str, Any] = {}

        if cluster_manager:
            checks["cluster_manager"] = await self.check_cluster_manager(cluster_manager)
        if coordinator:
            checks["coordinator"] = await self.check_coordinator(coordinator)
        if leader_election:
            checks["leader_election"] = await self.check_leader_election(leader_election)
        if heartbeat_monitor:
            checks["heartbeat"] = await self.check_heartbeat(heartbeat_monitor)
        if worker_registry:
            checks["worker_registry"] = await self.check_worker_registry(worker_registry)
        if failover_manager:
            checks["failover"] = await self.check_failover(failover_manager)
        if recovery_coordinator:
            checks["recovery"] = await self.check_recovery(recovery_coordinator)
        if quorum_manager:
            checks["quorum"] = await self.check_quorum(quorum_manager)
        if shard_manager:
            checks["shards"] = await self.check_shards(shard_manager)
        if scheduler:
            checks["scheduler"] = await self.check_scheduler(scheduler)

        all_healthy = all(c.get("healthy", False) for c in checks.values())

        return {
            "status": "healthy" if all_healthy else "degraded",
            "timestamp": self._last_check,
            "components": checks,
        }
