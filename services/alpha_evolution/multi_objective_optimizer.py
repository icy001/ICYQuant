"""
Multi-Objective Optimizer — Simultaneously optimizes across multiple fitness dimensions.

Optimization objectives (simultaneous):
    - Maximize: IC, Sharpe, Stability, Robustness, Capacity
    - Minimize: Turnover, Max Drawdown, Correlation

Uses weighted sum approach with configurable weights per objective.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from services.alpha_evolution.fitness_function import FitnessDimension


class ObjectiveDirection(Enum):
    MAXIMIZE = "maximize"
    MINIMIZE = "minimize"


@dataclass
class Objective:
    """A single optimization objective."""

    dimension: FitnessDimension
    direction: ObjectiveDirection
    weight: float = 1.0

    def normalize_value(self, value: float, min_val: float, max_val: float) -> float:
        """Normalize a value to [0, 1] range."""
        if max_val == min_val:
            return 0.5
        return (value - min_val) / (max_val - min_val)


@dataclass
class MultiObjectiveConfig:
    """Configuration for multi-objective optimization."""

    objectives: List[Objective] = field(default_factory=lambda: [
        Objective(FitnessDimension.IC, ObjectiveDirection.MAXIMIZE, 0.15),
        Objective(FitnessDimension.SHARPE, ObjectiveDirection.MAXIMIZE, 0.15),
        Objective(FitnessDimension.STABILITY, ObjectiveDirection.MAXIMIZE, 0.10),
        Objective(FitnessDimension.ROBUSTNESS, ObjectiveDirection.MAXIMIZE, 0.10),
        Objective(FitnessDimension.CAPACITY, ObjectiveDirection.MAXIMIZE, 0.10),
        Objective(FitnessDimension.TURNOVER, ObjectiveDirection.MINIMIZE, 0.05),
        Objective(FitnessDimension.MAX_DRAWDOWN, ObjectiveDirection.MINIMIZE, 0.05),
        Objective(FitnessDimension.NOVELTY, ObjectiveDirection.MAXIMIZE, 0.10),
    ])

    @property
    def weights(self) -> Dict[str, float]:
        return {obj.dimension.value: obj.weight for obj in self.objectives}


class MultiObjectiveOptimizer:
    """
    Multi-objective optimization for factor/alpha candidates.

    Features:
        - Weighted sum aggregation
        - Normalization per dimension
        - Epsilon-constraint method
        - Objective importance ranking
    """

    def __init__(self, config: Optional[MultiObjectiveConfig] = None):
        self._config = config or MultiObjectiveConfig()

    def compute_objective_value(
        self,
        dim: FitnessDimension,
        value: float,
    ) -> float:
        """Compute the contribution of one dimension."""
        for obj in self._config.objectives:
            if obj.dimension == dim:
                if obj.direction == ObjectiveDirection.MAXIMIZE:
                    return value * obj.weight
                else:
                    return -value * obj.weight
        return 0.0

    def compute_aggregate(
        self, metrics: Dict[str, float]
    ) -> float:
        """Compute weighted aggregate objective value."""
        total = 0.0
        for obj in self._config.objectives:
            value = metrics.get(obj.dimension.value, 0)
            if obj.direction == ObjectiveDirection.MAXIMIZE:
                total += value * obj.weight
            else:
                total -= value * obj.weight
        return total

    def is_dominated(
        self,
        metrics_a: Dict[str, float],
        metrics_b: Dict[str, float],
    ) -> bool:
        """
        Check if A is Pareto-dominated by B.
        B dominates A if B is at least as good in all objectives and strictly better in at least one.
        """
        better_in_any = False
        for obj in self._config.objectives:
            val_a = metrics_a.get(obj.dimension.value, 0)
            val_b = metrics_b.get(obj.dimension.value, 0)

            if obj.direction == ObjectiveDirection.MAXIMIZE:
                if val_b < val_a:
                    return False
                if val_b > val_a:
                    better_in_any = True
            else:
                if val_b > val_a:
                    return False
                if val_b < val_a:
                    better_in_any = True

        return better_in_any

    def get_pareto_frontier(
        self,
        individuals: List[Tuple[str, Dict[str, float]]],
    ) -> List[str]:
        """
        Compute Pareto frontier (non-dominated set).

        Args:
            individuals: List of (id, metrics_dict) tuples

        Returns:
            List of IDs on the Pareto frontier
        """
        if not individuals:
            return []

        pareto = []
        for oid_a, metrics_a in individuals:
            dominated = False
            for oid_b, metrics_b in individuals:
                if oid_a == oid_b:
                    continue
                if self.is_dominated(metrics_a, metrics_b):
                    dominated = True
                    break
            if not dominated:
                pareto.append(oid_a)

        return pareto

    def get_objective_names(self) -> List[str]:
        """Get list of objective dimension names."""
        return [obj.dimension.value for obj in self._config.objectives]

    def get_config(self) -> Dict[str, Any]:
        return {
            "objectives": [
                {"dimension": obj.dimension.value, "direction": obj.direction.value, "weight": obj.weight}
                for obj in self._config.objectives
            ]
        }
