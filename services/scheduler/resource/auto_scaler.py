"""Auto Scaler — elastic scale-out and scale-in based on cluster metrics.

The :class:`AutoScaler` monitors queue depth, CPU, memory, and latency
to decide when to add or remove nodes.  Designed to integrate with
Kubernetes HPA or cloud auto-scaling groups in production.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .resource_pool import ResourcePool

logger = logging.getLogger(__name__)


@dataclass
class ScalingResult:
    """Result of an auto-scaling evaluation."""

    action: str = "none"  # scale_out / scale_in / none
    current_nodes: int = 0
    target_nodes: int = 0
    reason: str = ""
    cpu_utilization_pct: float = 0.0
    memory_utilization_pct: float = 0.0
    queue_depth: int = 0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class AutoScaler:
    """Elastic auto-scaler for the scheduler cluster.

    Rules:
    * Scale out when: cpu > scale_out_cpu_pct OR memory > scale_out_mem_pct OR queue > scale_out_queue
    * Scale in when:  cpu < scale_in_cpu_pct AND memory < scale_in_mem_pct AND queue < scale_in_queue
    * Cooldown between scaling actions
    * Min/max node limits

    Usage::

        scaler = AutoScaler(pool, min_nodes=2, max_nodes=20)
        result = scaler.evaluate(queue_depth=500)
        if result.action == "scale_out":
            await scaler.scale_out(result.target_nodes)
    """

    def __init__(
        self, pool: ResourcePool, min_nodes: int = 1, max_nodes: int = 100,
        scale_out_cpu_pct: float = 75.0, scale_out_mem_pct: float = 80.0,
        scale_out_queue: int = 1000, scale_in_cpu_pct: float = 30.0,
        scale_in_mem_pct: float = 35.0, scale_in_queue: int = 50,
        cooldown_seconds: float = 120.0, step_size: int = 1,
    ) -> None:
        self._pool = pool
        self._min_nodes = min_nodes
        self._max_nodes = max_nodes
        self._scale_out_cpu = scale_out_cpu_pct
        self._scale_out_mem = scale_out_mem_pct
        self._scale_out_queue = scale_out_queue
        self._scale_in_cpu = scale_in_cpu_pct
        self._scale_in_mem = scale_in_mem_pct
        self._scale_in_queue = scale_in_queue
        self._cooldown = cooldown_seconds
        self._step_size = step_size

        self._last_scale_time: Optional[datetime] = None
        self._total_scale_outs: int = 0
        self._total_scale_ins: int = 0

    # ------------------------------------------------------------------
    # Evaluate
    # ------------------------------------------------------------------

    def evaluate(self, queue_depth: int = 0) -> ScalingResult:
        """Evaluate whether to scale out, scale in, or do nothing."""
        nodes = self._pool.list_nodes()
        current = len(nodes)
        util = self._pool.utilization()
        cpu_pct = util["cpu_pct"]
        mem_pct = util["memory_pct"]

        # Cooldown check
        if self._last_scale_time:
            elapsed = (datetime.now(timezone.utc) - self._last_scale_time).total_seconds()
            if elapsed < self._cooldown:
                return ScalingResult(
                    action="none", current_nodes=current, target_nodes=current,
                    reason=f"Cooldown ({elapsed:.0f}s < {self._cooldown}s)",
                    cpu_utilization_pct=cpu_pct, memory_utilization_pct=mem_pct,
                    queue_depth=queue_depth,
                )

        # Scale out
        if (
            cpu_pct > self._scale_out_cpu
            or mem_pct > self._scale_out_mem
            or queue_depth > self._scale_out_queue
        ):
            target = min(current + self._step_size, self._max_nodes)
            reason_parts = []
            if cpu_pct > self._scale_out_cpu:
                reason_parts.append(f"CPU {cpu_pct:.0f}% > {self._scale_out_cpu}%")
            if mem_pct > self._scale_out_mem:
                reason_parts.append(f"Memory {mem_pct:.0f}% > {self._scale_out_mem}%")
            if queue_depth > self._scale_out_queue:
                reason_parts.append(f"Queue {queue_depth} > {self._scale_out_queue}")
            return ScalingResult(
                action="scale_out", current_nodes=current, target_nodes=target,
                reason="; ".join(reason_parts),
                cpu_utilization_pct=cpu_pct, memory_utilization_pct=mem_pct,
                queue_depth=queue_depth,
            )

        # Scale in
        if (
            cpu_pct < self._scale_in_cpu
            and mem_pct < self._scale_in_mem
            and queue_depth < self._scale_in_queue
            and current > self._min_nodes
        ):
            # Only scale in if a node is nearly empty
            idle_nodes = sum(
                1 for n in nodes
                if n.cpu_used / max(n.cpu_total, 0.001) < 0.1
            )
            if idle_nodes > 0:
                target = max(current - min(self._step_size, idle_nodes), self._min_nodes)
                return ScalingResult(
                    action="scale_in", current_nodes=current, target_nodes=target,
                    reason=f"Low utilization, {idle_nodes} idle nodes",
                    cpu_utilization_pct=cpu_pct, memory_utilization_pct=mem_pct,
                    queue_depth=queue_depth,
                )

        return ScalingResult(
            action="none", current_nodes=current, target_nodes=current,
            reason="Within thresholds",
            cpu_utilization_pct=cpu_pct, memory_utilization_pct=mem_pct,
            queue_depth=queue_depth,
        )

    # ------------------------------------------------------------------
    # Execute
    # ------------------------------------------------------------------

    async def scale_out(self, target: int) -> int:
        """Add nodes to reach target count."""
        current = len(self._pool.list_nodes())
        to_add = target - current
        for i in range(to_add):
            node_id = f"auto-node-{self._total_scale_outs + i:03d}"
            self._pool.add_node(node_id, cpu=16, memory_mb=32768)
        self._total_scale_outs += to_add
        self._last_scale_time = datetime.now(timezone.utc)
        logger.info("AutoScaler: scaled out +%d nodes → %d total", to_add, target)
        return to_add

    async def scale_in(self, target: int) -> int:
        """Remove idle nodes to reach target count."""
        nodes = self._pool.list_nodes()
        idle = [
            n for n in nodes
            if n.cpu_used / max(n.cpu_total, 0.001) < 0.1
        ]
        to_remove = min(len(idle), len(nodes) - target)
        for node in idle[:to_remove]:
            self._pool.remove_node(node.node_id)
        self._total_scale_ins += to_remove
        self._last_scale_time = datetime.now(timezone.utc)
        logger.info("AutoScaler: scaled in -%d nodes → %d total", to_remove, len(self._pool.list_nodes()))
        return to_remove

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def health_report(self) -> Dict[str, Any]:
        return {
            "node_count": len(self._pool.list_nodes()),
            "min_nodes": self._min_nodes, "max_nodes": self._max_nodes,
            "total_scale_outs": self._total_scale_outs,
            "total_scale_ins": self._total_scale_ins,
            "last_scale_time": self._last_scale_time.isoformat() if self._last_scale_time else None,
        }
