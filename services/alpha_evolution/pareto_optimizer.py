"""
Pareto Optimizer — Pareto frontier-based multi-objective optimization.

Identifies and maintains the Pareto-optimal frontier across multiple objectives.
Key features:
    - Pareto dominance detection
    - Frontier maintenance across generations
    - Crowding distance (diversity along the frontier)
    - Hypervolume computation (frontier quality metric)
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Set, Tuple

from services.alpha_evolution.multi_objective_optimizer import (
    MultiObjectiveOptimizer,
    MultiObjectiveConfig,
    FitnessDimension,
    ObjectiveDirection,
)

logger = logging.getLogger(__name__)


class ParetoOptimizer:
    """
    Manages the Pareto frontier across evolution generations.

    Maintains the non-dominated set of solutions, tracks frontier
    metrics (size, hypervolume, crowding), and selects diverse
    solutions from the frontier.
    """

    def __init__(self, config: Optional[MultiObjectiveConfig] = None):
        self._optimizer = MultiObjectiveOptimizer(config)
        self._frontier_ids: Set[str] = set()
        self._frontier_history: List[Dict[str, Any]] = []

    # ── Frontier Computation ───────────────────────────────

    def compute_frontier(
        self,
        individuals: List[Tuple[str, Dict[str, float]]],
    ) -> List[str]:
        """
        Compute the Pareto frontier for the current population.

        Returns list of non-dominated individual IDs.
        """
        frontier = self._optimizer.get_pareto_frontier(individuals)
        self._frontier_ids = set(frontier)
        self._frontier_history.append({
            "size": len(frontier),
            "ids": list(frontier),
        })
        logger.debug("Pareto frontier size: %d", len(frontier))
        return frontier

    def update_frontier(
        self,
        candidates: List[Tuple[str, Dict[str, float]]],
        current_frontier: Optional[List[str]] = None,
    ) -> List[str]:
        """
        Update the frontier with new candidates.

        New candidates may:
            - Enter the frontier (dominate existing members)
            - Be rejected (dominated by existing members)
            - Expand the frontier (incomparable)
        """
        if current_frontier is None:
            current_frontier = list(self._frontier_ids)

        # Combine current frontier with new candidates
        all_ids = set(current_frontier + [cid for cid, _ in candidates])
        all_metrics = {cid: metrics for cid, metrics in candidates}

        # Recompute frontier
        all_individuals = [(oid, all_metrics.get(oid, {})) for oid in all_ids]
        new_frontier = self.compute_frontier(all_individuals)
        return new_frontier

    # ── Crowding Distance ──────────────────────────────────

    def compute_crowding_distance(
        self,
        frontier_ids: List[str],
        metrics: Dict[str, Dict[str, float]],
    ) -> Dict[str, float]:
        """
        Compute crowding distance for diversity along the Pareto frontier.

        Higher crowding distance = more isolated = higher diversity value.
        """
        if len(frontier_ids) <= 2:
            return {oid: float("inf") for oid in frontier_ids}

        distances: Dict[str, float] = {oid: 0.0 for oid in frontier_ids}
        objectives = self._optimizer.get_objective_names()

        for obj_name in objectives:
            # Sort by this objective
            sorted_ids = sorted(
                frontier_ids,
                key=lambda oid: metrics.get(oid, {}).get(obj_name, 0),
            )

            # Set boundary points to infinity
            distances[sorted_ids[0]] = float("inf")
            distances[sorted_ids[-1]] = float("inf")

            # Compute range
            min_val = metrics.get(sorted_ids[0], {}).get(obj_name, 0)
            max_val = metrics.get(sorted_ids[-1], {}).get(obj_name, 0)
            obj_range = max_val - min_val

            if obj_range == 0:
                continue

            # Interior points
            for i in range(1, len(sorted_ids) - 1):
                next_val = metrics.get(sorted_ids[i + 1], {}).get(obj_name, 0)
                prev_val = metrics.get(sorted_ids[i - 1], {}).get(obj_name, 0)
                distances[sorted_ids[i]] += (next_val - prev_val) / obj_range

        return distances

    # ── Selection from Frontier ─────────────────────────────

    def select_diverse_from_frontier(
        self,
        n: int,
        metrics: Dict[str, Dict[str, float]],
    ) -> List[str]:
        """
        Select N diverse solutions from the Pareto frontier.

        Uses crowding distance to prefer spread-out solutions.
        """
        if len(self._frontier_ids) <= n:
            return list(self._frontier_ids)

        distances = self.compute_crowding_distance(
            list(self._frontier_ids), metrics
        )
        sorted_by_distance = sorted(
            self._frontier_ids,
            key=lambda oid: distances.get(oid, 0),
            reverse=True,
        )
        return sorted_by_distance[:n]

    # ── Statistics ─────────────────────────────────────────

    def get_frontier_stats(self) -> Dict[str, Any]:
        """Get statistics about the current frontier."""
        history_sizes = [h["size"] for h in self._frontier_history[-50:]]
        return {
            "current_size": len(self._frontier_ids),
            "history_mean": sum(history_sizes) / len(history_sizes) if history_sizes else 0,
            "history_max": max(history_sizes) if history_sizes else 0,
            "growth_rate": (
                (history_sizes[-1] - history_sizes[0]) / len(history_sizes)
                if len(history_sizes) > 1 else 0
            ),
        }

    @property
    def frontier_ids(self) -> Set[str]:
        return self._frontier_ids

    @property
    def frontier_size(self) -> int:
        return len(self._frontier_ids)
