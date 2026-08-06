"""Cost Optimizer — balances performance, resource cost, and priority.

The :class:`CostOptimizer` evaluates placement decisions through a cost
lens, preferring cheaper nodes when performance requirements are met.
Designed for cloud environments where different instance types have
different hourly costs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class CostResult:
    """Result of cost-optimized placement analysis."""

    node_id: str
    estimated_cost_per_hour: float
    cpu_cost: float
    memory_cost: float
    gpu_cost: float
    total_score: float  # combined performance + cost score
    is_optimal: bool = False


@dataclass
class NodeCostProfile:
    """Cost profile for a node or instance type."""

    node_id: str
    cpu_cost_per_core_hour: float = 0.04  # $/core/hour
    memory_cost_per_gb_hour: float = 0.005  # $/GB/hour
    gpu_cost_per_unit_hour: float = 0.50  # $/GPU/hour
    base_cost_per_hour: float = 0.0  # fixed cost
    spot_discount: float = 0.0  # 0.0–1.0 discount for spot/preemptible
    labels: Dict[str, str] = field(default_factory=dict)


class CostOptimizer:
    """Cost-aware placement optimizer.

    Usage::

        opt = CostOptimizer()
        opt.register_node_cost("node-1", cpu_cost=0.04, memory_cost=0.005)
        result = opt.optimize(candidates, cpu_request=4, memory_mb=8192)
    """

    def __init__(self, performance_weight: float = 0.5, cost_weight: float = 0.5) -> None:
        self._perf_weight = performance_weight
        self._cost_weight = cost_weight
        self._profiles: Dict[str, NodeCostProfile] = {}

    # ------------------------------------------------------------------
    # Cost profiles
    # ------------------------------------------------------------------

    def register_node_cost(
        self, node_id: str, cpu_cost_per_core_hour: float = 0.04,
        memory_cost_per_gb_hour: float = 0.005,
        gpu_cost_per_unit_hour: float = 0.50,
        base_cost_per_hour: float = 0.0, spot_discount: float = 0.0,
        labels: Optional[Dict[str, str]] = None,
    ) -> None:
        self._profiles[node_id] = NodeCostProfile(
            node_id=node_id,
            cpu_cost_per_core_hour=cpu_cost_per_core_hour,
            memory_cost_per_gb_hour=memory_cost_per_gb_hour,
            gpu_cost_per_unit_hour=gpu_cost_per_unit_hour,
            base_cost_per_hour=base_cost_per_hour,
            spot_discount=spot_discount,
            labels=labels or {},
        )

    # ------------------------------------------------------------------
    # Optimize
    # ------------------------------------------------------------------

    def estimate_cost(
        self, node_id: str, cpu_request: float,
        memory_mb_request: float, gpu_request: float = 0.0,
    ) -> float:
        """Estimate hourly cost for a job on a node."""
        profile = self._profiles.get(node_id)
        if profile is None:
            # Default cost estimate
            return cpu_request * 0.04 + (memory_mb_request / 1024) * 0.005 + gpu_request * 0.50

        cost = (
            profile.base_cost_per_hour
            + cpu_request * profile.cpu_cost_per_core_hour
            + (memory_mb_request / 1024) * profile.memory_cost_per_gb_hour
            + gpu_request * profile.gpu_cost_per_unit_hour
        )
        # Apply spot discount
        if profile.spot_discount > 0:
            cost *= (1.0 - profile.spot_discount)
        return cost

    def optimize(
        self, candidates: List[Tuple[str, float]],
        cpu_request: float, memory_mb_request: float,
        gpu_request: float = 0.0,
    ) -> List[CostResult]:
        """Rank candidate nodes by combined performance+cost score.

        Args:
            candidates: List of (node_id, performance_score)

        Returns:
            Sorted list of CostResult (best first).
        """
        if not candidates:
            return []

        max_perf = max(s for _, s in candidates) if candidates else 1.0

        results = []
        for node_id, perf_score in candidates:
            cost = self.estimate_cost(node_id, cpu_request, memory_mb_request, gpu_request)

            # Normalize scores
            perf_norm = perf_score / max(max_perf, 0.001)
            cost_norm = 1.0 / max(cost, 0.001)  # inverse: cheaper = higher score

            # Combined score
            total = self._perf_weight * perf_norm + self._cost_weight * cost_norm

            results.append(CostResult(
                node_id=node_id,
                estimated_cost_per_hour=cost,
                cpu_cost=cpu_request * self._profiles.get(node_id, NodeCostProfile(node_id)).cpu_cost_per_core_hour,
                memory_cost=(memory_mb_request / 1024) * self._profiles.get(node_id, NodeCostProfile(node_id)).memory_cost_per_gb_hour,
                gpu_cost=gpu_request * self._profiles.get(node_id, NodeCostProfile(node_id)).gpu_cost_per_unit_hour,
                total_score=total,
            ))

        results.sort(key=lambda r: r.total_score, reverse=True)
        if results:
            results[0].is_optimal = True
        return results

    def get_cheapest_node(
        self, cpu_request: float, memory_mb_request: float,
        gpu_request: float = 0.0,
    ) -> Optional[str]:
        """Return the cheapest node that satisfies the request."""
        best_node: Optional[str] = None
        best_cost = float("inf")
        for node_id in self._profiles:
            cost = self.estimate_cost(node_id, cpu_request, memory_mb_request, gpu_request)
            if cost < best_cost:
                best_cost = cost
                best_node = node_id
        return best_node

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def health_report(self) -> Dict[str, Any]:
        return {
            "nodes_with_profiles": len(self._profiles),
            "performance_weight": self._perf_weight,
            "cost_weight": self._cost_weight,
        }
