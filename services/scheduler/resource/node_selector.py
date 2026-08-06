"""Node Selector — selects the best node(s) for job placement.

The :class:`NodeSelector` combines filtering + scoring to pick the optimal
node(s) for a given job request.  Supports pluggable selection strategies.
"""

from __future__ import annotations

import enum
from typing import Any, Dict, List, Optional

from .node_inventory import NodeInventory, NodeRecord, NodeStatus
from .node_score import NodeScoringEngine, NodeScore


class SelectionStrategy(str, enum.Enum):
    """Node selection strategies."""

    LEAST_LOADED = "least_loaded"
    BALANCED = "balanced"
    LATENCY_FIRST = "latency_first"
    GPU_FIRST = "gpu_first"
    COST_FIRST = "cost_first"


class NodeSelector:
    """Selects the best node for job placement.

    Usage::

        selector = NodeSelector(inventory)
        node = selector.select(
            cpu_cores=4, memory_mb=8192,
            strategy=SelectionStrategy.BALANCED,
            region="us-east",
        )
    """

    def __init__(self, inventory: NodeInventory) -> None:
        self._inventory = inventory
        self._scorer = NodeScoringEngine()

    # ------------------------------------------------------------------
    # Select
    # ------------------------------------------------------------------

    def select(
        self, cpu_cores: float = 0.0, memory_mb: float = 0.0,
        gpu_units: float = 0.0, strategy: SelectionStrategy = SelectionStrategy.BALANCED,
        region: Optional[str] = None, zone: Optional[str] = None,
        preferred_nodes: Optional[List[str]] = None,
        required_labels: Optional[Dict[str, str]] = None,
    ) -> Optional[NodeRecord]:
        """Select the best single node for a job."""
        candidates = self._filter_candidates(
            cpu_cores, memory_mb, gpu_units,
            region, zone, required_labels,
        )
        if not candidates:
            return None

        # Adjust scorer weights based on strategy
        self._apply_strategy(strategy)

        score = self._scorer.best_node(
            candidates, cpu_cores, memory_mb, preferred_nodes,
        )
        if score is None:
            return None

        return self._inventory.get(score.node_id)

    def select_top_n(
        self, n: int = 3, cpu_cores: float = 0.0, memory_mb: float = 0.0,
        strategy: SelectionStrategy = SelectionStrategy.BALANCED,
        region: Optional[str] = None, zone: Optional[str] = None,
        preferred_nodes: Optional[List[str]] = None,
    ) -> List[NodeScore]:
        """Select the top N nodes, ranked by score."""
        candidates = self._filter_candidates(cpu_cores, memory_mb, 0.0, region, zone)
        if not candidates:
            return []

        self._apply_strategy(strategy)
        scores = self._scorer.score_nodes(candidates, cpu_cores, memory_mb, preferred_nodes)
        return scores[:n]

    # ------------------------------------------------------------------
    # Filter
    # ------------------------------------------------------------------

    def _filter_candidates(
        self, cpu_cores: float, memory_mb: float, gpu_units: float,
        region: Optional[str], zone: Optional[str],
        labels: Optional[Dict[str, str]] = None,
    ) -> List[NodeRecord]:
        candidates = self._inventory.filter(
            region=region, zone=zone, status=NodeStatus.ONLINE,
            min_cpu=cpu_cores, min_memory_mb=memory_mb,
            gpu_required=(gpu_units > 0), labels=labels,
        )
        return candidates

    # ------------------------------------------------------------------
    # Strategy
    # ------------------------------------------------------------------

    def _apply_strategy(self, strategy: SelectionStrategy) -> None:
        """Tune scorer weights per strategy."""
        if strategy == SelectionStrategy.LEAST_LOADED:
            self._scorer.set_weights(load=0.40, cpu=0.25, memory=0.20, latency=0.10, failure=0.05, affinity=0.00)
        elif strategy == SelectionStrategy.LATENCY_FIRST:
            self._scorer.set_weights(latency=0.50, cpu=0.20, memory=0.15, load=0.10, failure=0.05, affinity=0.00)
        elif strategy == SelectionStrategy.GPU_FIRST:
            self._scorer.set_weights(cpu=0.30, memory=0.20, latency=0.10, load=0.10, failure=0.05, affinity=0.25)
        elif strategy == SelectionStrategy.COST_FIRST:
            self._scorer.set_weights(cpu=0.20, memory=0.20, latency=0.10, load=0.30, failure=0.15, affinity=0.05)
        else:  # BALANCED (default)
            self._scorer.set_weights(cpu=0.30, memory=0.25, latency=0.15, load=0.15, failure=0.10, affinity=0.05)

    def health_report(self) -> Dict[str, Any]:
        return {
            "nodes_available": self._inventory.count(),
            "online": self._inventory.count_by_status().get("online", 0),
            "scorer": self._scorer.health_report(),
        }
