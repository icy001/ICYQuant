"""Cluster Diagnostics — inspection and troubleshooting for the workflow cluster.

Provides tools for:

* Cluster topology inspection
* Node health diagnostics
* Shard distribution analysis
* Failover event analysis
* Recovery audit trail
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ClusterDiagnostics:
    """Diagnostic tools for the workflow cluster.

    Usage::

        diag = ClusterDiagnostics()
        report = await diag.full_diagnostic(cluster_manager, node_registry, shard_manager)
    """

    # ------------------------------------------------------------------
    # Topology
    # ------------------------------------------------------------------

    async def inspect_topology(
        self,
        cluster_manager,
        node_registry,
    ) -> Dict[str, Any]:
        """Inspect the cluster topology."""
        nodes = await node_registry.list_nodes()
        leader = await node_registry.get_leader()

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "total_nodes": len(nodes),
            "leader": leader.node_id if leader else None,
            "nodes": [
                {
                    "node_id": n.node_id,
                    "role": n.role.value,
                    "status": n.status.value,
                    "address": n.address,
                    "resources": n.resources.to_dict(),
                    "last_heartbeat": n.last_heartbeat.isoformat() if n.last_heartbeat else None,
                }
                for n in nodes
            ],
        }

    # ------------------------------------------------------------------
    # Node health
    # ------------------------------------------------------------------

    async def inspect_node_health(
        self,
        node_id: str,
        node_registry,
        heartbeat_monitor,
    ) -> Dict[str, Any]:
        """Inspect the health of a specific node."""
        node = await node_registry.get(node_id)
        if node is None:
            return {"node_id": node_id, "found": False}

        record = heartbeat_monitor.get_record(node_id) if heartbeat_monitor else None

        return {
            "node_id": node_id,
            "found": True,
            "role": node.role.value,
            "status": node.status.value,
            "resources": node.resources.to_dict(),
            "heartbeat": {
                "alive": record.is_alive if record else None,
                "missed_beats": record.missed_count if record else 0,
                "latency_ms": record.latency_ms if record else 0,
            } if record else None,
        }

    # ------------------------------------------------------------------
    # Shard analysis
    # ------------------------------------------------------------------

    async def inspect_shards(self, shard_manager) -> Dict[str, Any]:
        """Analyze shard distribution."""
        shards = await shard_manager.list_shards()
        distribution = await shard_manager.shard_distribution()

        total = sum(distribution.values())
        avg = total / max(1, len(distribution))
        max_count = max(distribution.values()) if distribution else 0
        min_count = min(distribution.values()) if distribution else 0

        return {
            "total_shards": len(shards),
            "total_workflows": total,
            "avg_workflows_per_shard": round(avg, 2),
            "max_workflows_per_shard": max_count,
            "min_workflows_per_shard": min_count,
            "imbalance": round(max_count - min_count, 2),
            "distribution": distribution,
        }

    # ------------------------------------------------------------------
    # Failover analysis
    # ------------------------------------------------------------------

    async def inspect_failovers(
        self,
        failover_manager,
        limit: int = 50,
    ) -> Dict[str, Any]:
        """Analyze recent failover events."""
        history = await failover_manager.get_failover_history(limit=limit)

        total = len(history)
        completed = sum(1 for h in history if h.state == "completed")
        failed = sum(1 for h in history if h.state == "failed")
        total_affected = sum(len(h.affected_executions) for h in history)
        total_recovered = sum(len(h.recovered_executions) for h in history)

        return {
            "total_failovers": total,
            "completed": completed,
            "failed": failed,
            "success_rate": round(completed / max(1, total), 4),
            "total_affected_executions": total_affected,
            "total_recovered_executions": total_recovered,
            "recovery_rate": round(total_recovered / max(1, total_affected), 4),
            "recent": [
                {
                    "failover_id": h.failover_id,
                    "node": h.failed_node_id,
                    "state": h.state,
                    "affected": len(h.affected_executions),
                    "recovered": len(h.recovered_executions),
                    "duration_seconds": round(h.duration_seconds, 3),
                }
                for h in history[-10:]
            ],
        }

    # ------------------------------------------------------------------
    # Recovery audit
    # ------------------------------------------------------------------

    async def inspect_recoveries(
        self,
        recovery_coordinator,
        limit: int = 50,
    ) -> Dict[str, Any]:
        """Analyze recent recovery operations."""
        history = await recovery_coordinator.get_recovery_history(limit=limit)

        total = len(history)
        completed = sum(1 for h in history if h.phase == "complete")
        failed = sum(1 for h in history if h.phase == "failed")

        return {
            "total_recoveries": total,
            "completed": completed,
            "failed": failed,
            "success_rate": round(completed / max(1, total), 4),
            "avg_duration_seconds": round(
                sum(h.duration_seconds for h in history) / max(1, total), 3
            ),
            "recent": [
                {
                    "task_id": h.task_id,
                    "execution_id": h.execution_id,
                    "phase": h.phase,
                    "assigned_node": h.assigned_node_id,
                    "duration_seconds": round(h.duration_seconds, 3),
                }
                for h in history[-10:]
            ],
        }

    # ------------------------------------------------------------------
    # Full diagnostic
    # ------------------------------------------------------------------

    async def full_diagnostic(
        self,
        cluster_manager,
        node_registry,
        shard_manager,
        failover_manager=None,
        recovery_coordinator=None,
        heartbeat_monitor=None,
    ) -> Dict[str, Any]:
        """Run a full cluster diagnostic."""
        report: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat(),
            "topology": await self.inspect_topology(cluster_manager, node_registry),
            "shards": await self.inspect_shards(shard_manager),
        }

        if failover_manager:
            report["failovers"] = await self.inspect_failovers(failover_manager)

        if recovery_coordinator:
            report["recoveries"] = await self.inspect_recoveries(recovery_coordinator)

        return report
