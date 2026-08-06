"""Cluster Health — aggregated health checks for the scheduler cluster.

The :class:`ClusterHealth` aggregates health reports from the cluster
manager, coordinator, election, queue, replication, and failover manager
into a single status object suitable for monitoring dashboards.
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class ClusterHealth:
    """Aggregated health checker for the scheduler cluster.

    Usage::

        health = ClusterHealth()
        status = health.check(
            cluster_manager=manager,
            coordinator=coordinator,
            election=election,
            queue=queue,
        )
    """

    # Healthy thresholds
    MIN_ONLINE_NODES_RATIO = 0.5
    MAX_QUEUE_DEPTH_PER_NODE = 5000
    MAX_DLQ_RATIO = 0.1
    MAX_MISSED_HEARTBEATS = 3

    def check(
        self,
        *,
        cluster_manager: Any = None,
        coordinator: Any = None,
        election: Any = None,
        queue: Any = None,
        replication: Any = None,
        failover_mgr: Any = None,
    ) -> Dict[str, Any]:
        """Run all health checks and return an aggregated status.

        Returns:
            Dict with overall status, component statuses, and details.
        """
        components: Dict[str, Dict[str, Any]] = {}
        unhealthy_count = 0

        # 1. Cluster Manager
        if cluster_manager:
            cm_status = self._check_cluster_manager(cluster_manager)
            components["cluster_manager"] = cm_status
            if cm_status["status"] == "unhealthy":
                unhealthy_count += 1

        # 2. Coordinator
        if coordinator:
            co_status = self._check_coordinator(coordinator)
            components["coordinator"] = co_status
            if co_status["status"] == "unhealthy":
                unhealthy_count += 1

        # 3. Leader Election
        if election:
            el_status = self._check_election(election)
            components["leader_election"] = el_status
            if el_status["status"] == "unhealthy":
                unhealthy_count += 1

        # 4. Queue
        if queue:
            q_status = self._check_queue(queue)
            components["queue"] = q_status
            if q_status["status"] == "unhealthy":
                unhealthy_count += 1

        # 5. Replication
        if replication:
            r_status = self._check_replication(replication)
            components["replication"] = r_status
            if r_status["status"] == "unhealthy":
                unhealthy_count += 1

        # 6. Failover Manager
        if failover_mgr:
            fm_status = self._check_failover(failover_mgr)
            components["failover"] = fm_status
            if fm_status["status"] == "unhealthy":
                unhealthy_count += 1

        # Aggregate
        if unhealthy_count > 0:
            overall = "unhealthy"
        elif any(c.get("status") == "degraded" for c in components.values()):
            overall = "degraded"
        else:
            overall = "healthy"

        return {
            "overall": overall,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "components": components,
            "unhealthy_count": unhealthy_count,
            "total_components": len(components),
        }

    # ------------------------------------------------------------------
    # Component Checks
    # ------------------------------------------------------------------

    def _check_cluster_manager(self, mgr: Any) -> Dict[str, Any]:
        state = getattr(mgr, "state", "unknown")
        member_count = getattr(mgr, "member_count", 0)

        status = "healthy"
        if state == "error":
            status = "unhealthy"
        elif state in ("degraded", "rebalancing"):
            status = "degraded"
        elif member_count == 0:
            status = "degraded"

        return {
            "status": status,
            "state": state,
            "member_count": member_count,
        }

    def _check_coordinator(self, coord: Any) -> Dict[str, Any]:
        role = getattr(coord, "role", "unknown")
        has_leader = getattr(coord, "leader_id", None) is not None

        status = "healthy"
        if not has_leader:
            status = "degraded"

        return {
            "status": status,
            "role": role,
            "has_leader": has_leader,
        }

    def _check_election(self, election: Any) -> Dict[str, Any]:
        has_leader = getattr(election, "leader_id", None) is not None
        is_running = getattr(election, "is_running", False)

        status = "healthy"
        if not is_running:
            status = "unhealthy"
        elif not has_leader:
            status = "degraded"

        return {
            "status": status,
            "leader_id": getattr(election, "leader_id", None),
            "is_running": is_running,
        }

    def _check_queue(self, queue: Any) -> Dict[str, Any]:
        depth = getattr(queue, "depth", 0)
        dlq = getattr(queue, "dlq_depth", 0)

        status = "healthy"
        if dlq > depth * self.MAX_DLQ_RATIO and depth > 0:
            status = "degraded"
        if depth > self.MAX_QUEUE_DEPTH_PER_NODE:
            status = "degraded"

        return {
            "status": status,
            "depth": depth,
            "dlq_depth": dlq,
        }

    def _check_replication(self, repl: Any) -> Dict[str, Any]:
        is_running = getattr(repl, "is_running", False)

        status = "healthy"
        if not is_running:
            status = "degraded"

        return {
            "status": status,
            "is_running": is_running,
        }

    def _check_failover(self, fm: Any) -> Dict[str, Any]:
        state = getattr(fm, "state", "unknown")

        status = "healthy"
        if state == "failover_in_progress":
            status = "degraded"

        return {
            "status": status,
            "state": state,
        }
