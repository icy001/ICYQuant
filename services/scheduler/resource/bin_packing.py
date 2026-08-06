"""Bin Packing Optimizer — packs jobs efficiently to minimize resource fragmentation.

The :class:`BinPackingOptimizer` consolidates workloads onto fewer nodes
to reduce resource fragmentation, improve utilization, and lower cost.
Uses a best-fit-decreasing heuristic.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .resource_pool import ResourcePool

logger = logging.getLogger(__name__)


@dataclass
class PackingResult:
    """Result of a bin-packing optimization pass."""

    nodes_before: int
    nodes_after: int
    utilization_before: float
    utilization_after: float
    migrations: int  # jobs moved
    freed_nodes: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)


@dataclass
class _BinItem:
    """An item to pack (a job or workload)."""

    item_id: str
    cpu: float
    memory_mb: float
    gpu: float = 0.0
    node_id: str = ""


class BinPackingOptimizer:
    """Optimizes job placement to minimize resource fragmentation.

    Uses a Best-Fit-Decreasing (BFD) heuristic:
    1. Sort jobs by resource size descending
    2. Place each job in the node with the least remaining space that fits

    Usage::

        optimizer = BinPackingOptimizer(pool, inventory)
        result = optimizer.optimize()
    """

    def __init__(self, pool: ResourcePool, inventory: Any = None) -> None:
        self._pool = pool
        self._inventory = inventory

    # ------------------------------------------------------------------
    # Optimize
    # ------------------------------------------------------------------

    def optimize(self) -> PackingResult:
        """Run a full bin-packing optimization pass.

        Returns a plan (does NOT execute migrations — callers must decide).
        """
        nodes = self._pool.list_nodes()
        nodes_before = len([n for n in nodes if n.cpu_used > 0])

        util_before = self._pool.utilization()

        # Collect all active "items" (approximation from node usage)
        items = self._collect_items(nodes)

        if len(items) < 2:
            return PackingResult(
                nodes_before=nodes_before, nodes_after=nodes_before,
                utilization_before=util_before.get("cpu_pct", 0),
                utilization_after=util_before.get("cpu_pct", 0),
                migrations=0,
                recommendations=["Too few items to optimize"],
            )

        # Best-Fit-Decreasing
        migrations, freed = self._best_fit_decreasing(items, nodes)

        nodes_after = nodes_before - len(freed)
        util_after = self._pool.utilization()

        recs: List[str] = []
        if migrations > 0:
            recs.append(f"Migrate {migrations} jobs to free {len(freed)} nodes")
        if nodes_after < nodes_before:
            recs.append(f"Can power down {len(freed)} underutilized nodes")
        if not recs:
            recs.append("Placement is already optimal")

        return PackingResult(
            nodes_before=nodes_before, nodes_after=nodes_after,
            utilization_before=util_before.get("cpu_pct", 0),
            utilization_after=util_after.get("cpu_pct", 0),
            migrations=migrations, freed_nodes=freed,
            recommendations=recs,
        )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _collect_items(self, nodes: list) -> List[_BinItem]:
        """Collect approximate items from node usage data."""
        items: List[_BinItem] = []
        for node in nodes:
            if node.cpu_used <= 0:
                continue
            # Treat each node's usage as one aggregated item
            items.append(_BinItem(
                item_id=f"{node.node_id}-item",
                cpu=node.cpu_used, memory_mb=node.memory_used_mb,
                gpu=node.gpu_used, node_id=node.node_id,
            ))
        return items

    def _best_fit_decreasing(
        self, items: List[_BinItem], nodes: list,
    ) -> Tuple[int, List[str]]:
        """Best-Fit-Decreasing algorithm. Returns (migration_count, freed_node_ids)."""
        # Sort items by CPU descending
        sorted_items = sorted(items, key=lambda i: i.cpu, reverse=True)

        # Initialize bins from current nodes (capacity unused)
        bins: Dict[str, Dict[str, float]] = {}
        for node in nodes:
            bins[node.node_id] = {
                "cpu_capacity": node.cpu_total,
                "cpu_used": 0.0,
                "mem_capacity": node.memory_total_mb,
                "mem_used": 0.0,
            }

        migrations = 0
        for item in sorted_items:
            # Find best-fit bin
            best_bin: Optional[str] = None
            best_remainder = float("inf")

            for node_id, b in bins.items():
                cpu_remain = b["cpu_capacity"] - b["cpu_used"] - item.cpu
                mem_remain = b["mem_capacity"] - b["mem_used"] - item.memory_mb
                if cpu_remain >= 0 and mem_remain >= 0:
                    waste = cpu_remain + mem_remain / 1024
                    if waste < best_remainder:
                        best_remainder = waste
                        best_bin = node_id

            if best_bin is None:
                continue  # Can't fit — leave on current node

            if best_bin != item.node_id:
                migrations += 1

            bins[best_bin]["cpu_used"] += item.cpu
            bins[best_bin]["mem_used"] += item.memory_mb

        # Find empty nodes that can be freed
        freed = [
            nid for nid, b in bins.items()
            if b["cpu_used"] <= 0.01
        ]

        return migrations, freed

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def health_report(self) -> Dict[str, Any]:
        return {"status": "ready"}
