"""Queue Rebalancer — automatically redistributes queue load across cluster nodes.

The :class:`QueueRebalancer` detects load imbalances across nodes and
generates rebalancing plans to move queue partitions between nodes.
It triggers on node join/leave events and periodic health checks.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class RebalancePlan:
    """A plan describing partition movements for rebalancing."""

    def __init__(self) -> None:
        self.plan_id: str = ""
        self.movements: List[Dict[str, Any]] = []
        self.source_node: str = ""
        self.target_node: str = ""
        self.partitions_to_move: int = 0
        self.estimated_impact: str = "low"
        self.created_at = datetime.now(timezone.utc)

    @property
    def is_empty(self) -> bool:
        return self.partitions_to_move == 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "movements": self.movements,
            "source_node": self.source_node,
            "target_node": self.target_node,
            "partitions_to_move": self.partitions_to_move,
            "estimated_impact": self.estimated_impact,
            "created_at": self.created_at.isoformat(),
        }


class QueueRebalancer:
    """Automatically rebalances queue partitions across nodes.

    Triggers:
    - Node joins the cluster → redistribute partitions
    - Node leaves the cluster → reassign orphaned partitions
    - Periodic imbalance check → incremental rebalancing

    Usage::

        rebalancer = QueueRebalancer(partitioner=partitioner)
        plan = await rebalancer.compute_plan(node_loads={"s1": 100, "s2": 20})
        await rebalancer.execute(plan)
    """

    def __init__(
        self,
        *,
        imbalance_threshold_pct: float = 30.0,
        max_partitions_per_move: int = 8,
        cooldown_seconds: float = 60.0,
    ) -> None:
        self._imbalance_threshold = imbalance_threshold_pct
        self._max_partitions_per_move = max_partitions_per_move
        self._cooldown = cooldown_seconds
        self._lock = threading.Lock()

        self._last_rebalance: Optional[datetime] = None
        self._rebalance_count: int = 0

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def last_rebalance(self) -> Optional[datetime]:
        return self._last_rebalance

    @property
    def rebalance_count(self) -> int:
        return self._rebalance_count

    # ------------------------------------------------------------------
    # Rebalancing
    # ------------------------------------------------------------------

    async def compute_plan(
        self,
        node_loads: Dict[str, float],
        *,
        node_partitions: Optional[Dict[str, List[int]]] = None,
    ) -> RebalancePlan:
        """Compute a rebalancing plan based on current node loads.

        Args:
            node_loads: Mapping of node_id → load metric (e.g., queue depth).
            node_partitions: Mapping of node_id → list of partition IDs.

        Returns:
            A RebalancePlan with recommended partition movements.
        """
        if len(node_loads) < 2:
            return RebalancePlan()

        avg_load = sum(node_loads.values()) / len(node_loads)
        if avg_load == 0:
            return RebalancePlan()

        plan = RebalancePlan()
        plan.plan_id = f"rb-{self._rebalance_count + 1}"

        # Find most loaded and least loaded nodes
        sorted_nodes = sorted(node_loads.items(), key=lambda x: x[1], reverse=True)
        most_loaded = sorted_nodes[0]
        least_loaded = sorted_nodes[-1]

        imbalance_pct = ((most_loaded[1] - least_loaded[1]) / avg_load) * 100

        if imbalance_pct < self._imbalance_threshold:
            logger.debug("Load balanced [imbalance=%.1f%%], no rebalance needed", imbalance_pct)
            return plan

        plan.source_node = most_loaded[0]
        plan.target_node = least_loaded[0]
        plan.partitions_to_move = min(
            int((most_loaded[1] - avg_load) / max(avg_load, 1)),
            self._max_partitions_per_move,
        )

        if node_partitions and most_loaded[0] in node_partitions:
            source_partitions = node_partitions[most_loaded[0]]
            for i in range(plan.partitions_to_move):
                if i < len(source_partitions):
                    plan.movements.append({
                        "partition": source_partitions[i],
                        "from_node": most_loaded[0],
                        "to_node": least_loaded[0],
                    })

        if plan.partitions_to_move > 0:
            plan.estimated_impact = "high" if imbalance_pct > 60 else "medium"

        logger.info(
            "Rebalance plan computed [%s→%s, partitions=%d, imbalance=%.1f%%]",
            plan.source_node, plan.target_node, plan.partitions_to_move, imbalance_pct,
        )
        return plan

    async def execute(self, plan: RebalancePlan) -> bool:
        """Execute a rebalancing plan.

        Returns:
            True if executed successfully.
        """
        if plan.is_empty:
            return True

        # Check cooldown
        if self._last_rebalance:
            elapsed = (datetime.now(timezone.utc) - self._last_rebalance).total_seconds()
            if elapsed < self._cooldown:
                logger.debug("Rebalance cooldown active [%.1fs remaining]", self._cooldown - elapsed)
                return False

        logger.info("Executing rebalance plan [id=%s, movements=%d]",
                     plan.plan_id, len(plan.movements))

        for movement in plan.movements:
            logger.debug(
                "Moving partition %d from %s to %s",
                movement["partition"], movement["from_node"], movement["to_node"],
            )

        with self._lock:
            self._last_rebalance = datetime.now(timezone.utc)
            self._rebalance_count += 1

        logger.info("Rebalance plan executed [id=%s]", plan.plan_id)
        return True

    async def on_node_join(self, node_id: str, node_loads: Dict[str, float]) -> Optional[RebalancePlan]:
        """Handle a node joining the cluster by computing a rebalance plan."""
        logger.info("Node %s joined, computing rebalance plan", node_id)
        plan = await self.compute_plan(node_loads)
        if not plan.is_empty:
            await self.execute(plan)
        return plan

    async def on_node_leave(self, node_id: str, node_loads: Dict[str, float]) -> Optional[RebalancePlan]:
        """Handle a node leaving the cluster by redistributing its load."""
        logger.info("Node %s left, computing rebalance plan", node_id)
        plan = await self.compute_plan(node_loads)
        if not plan.is_empty:
            await self.execute(plan)
        return plan

    async def check_and_rebalance(self, node_loads: Dict[str, float]) -> Optional[RebalancePlan]:
        """Periodic check for imbalance and trigger rebalancing if needed."""
        plan = await self.compute_plan(node_loads)
        if not plan.is_empty:
            await self.execute(plan)
        return plan

    def get_rebalancer_info(self) -> Dict[str, Any]:
        """Return rebalancer status summary."""
        return {
            "imbalance_threshold_pct": self._imbalance_threshold,
            "max_partitions_per_move": self._max_partitions_per_move,
            "cooldown_seconds": self._cooldown,
            "last_rebalance": self._last_rebalance.isoformat() if self._last_rebalance else None,
            "rebalance_count": self._rebalance_count,
        }
