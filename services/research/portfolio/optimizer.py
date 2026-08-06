"""Optimizer — abstract base and shared types for portfolio optimization.

Defines the common optimizer interface and result types used by
all optimization methods (MV, RP, BL, HRP).
"""

from __future__ import annotations

import abc
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class OptimizerType(str, Enum):
    """Supported optimizer types."""

    MEAN_VARIANCE = "mean_variance"
    RISK_PARITY = "risk_parity"
    BLACK_LITTERMAN = "black_litterman"
    HRP = "hierarchical_risk_parity"


class OptimizeStatus(str, Enum):
    """Optimization result status."""

    OPTIMAL = "optimal"
    FEASIBLE = "feasible"
    INFEASIBLE = "infeasible"
    UNBOUNDED = "unbounded"
    MAX_ITERATIONS = "max_iterations"
    ERROR = "error"


@dataclass
class OptimizeResult:
    """Standard optimization result."""

    weights: Dict[str, float]
    optimizer_type: OptimizerType = OptimizerType.MEAN_VARIANCE
    status: OptimizeStatus = OptimizeStatus.FEASIBLE
    expected_return: float = 0.0
    expected_risk: float = 0.0
    sharpe_ratio: float = 0.0
    iterations: int = 0
    objective_value: float = 0.0
    constraints_satisfied: bool = True
    messages: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "weights": self.weights,
            "optimizer_type": self.optimizer_type.value,
            "status": self.status.value,
            "expected_return": self.expected_return,
            "expected_risk": self.expected_risk,
            "sharpe_ratio": self.sharpe_ratio,
            "iterations": self.iterations,
            "objective_value": self.objective_value,
            "constraints_satisfied": self.constraints_satisfied,
            "messages": self.messages,
            "num_assets": len(self.weights),
            "metadata": self.metadata,
        }


class Optimizer(abc.ABC):
    """Abstract base class for portfolio optimizers.

    All optimizers follow the interface::

        optimizer = ConcreteOptimizer(cov_matrix, expected_returns, constraints)
        result = await optimizer.optimize()
    """

    def __init__(
        self,
        cov_matrix: Optional[Dict[str, Dict[str, float]]] = None,
        expected_returns: Optional[Dict[str, float]] = None,
        constraints: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        self._cov_matrix = cov_matrix or {}
        self._expected_returns = expected_returns or {}
        self._constraints = constraints or {}
        self._kwargs = kwargs

    @abc.abstractmethod
    async def optimize(self) -> OptimizeResult:
        """Run optimization and return result."""
        ...

    @property
    def assets(self) -> List[str]:
        """Get list of assets in the optimization."""
        return sorted(self._cov_matrix.keys())

    def _compute_portfolio_return(self, weights: Dict[str, float]) -> float:
        """Compute expected portfolio return."""
        return sum(
            weights.get(asset, 0.0) * self._expected_returns.get(asset, 0.0)
            for asset in weights
        )

    def _compute_portfolio_risk(self, weights: Dict[str, float]) -> float:
        """Compute portfolio variance."""
        assets = list(weights.keys())
        variance = 0.0
        for i in assets:
            for j in assets:
                wi = weights.get(i, 0.0)
                wj = weights.get(j, 0.0)
                cov_ij = (
                    self._cov_matrix.get(i, {}).get(j, 0.0)
                    if i in self._cov_matrix
                    else 0.0
                )
                variance += wi * wj * cov_ij
        return max(variance, 0.0)

    def _compute_sharpe(self, ret: float, risk: float) -> float:
        """Compute Sharpe ratio (assuming risk-free = 0)."""
        if risk <= 0:
            return 0.0
        return ret / (risk ** 0.5)

    def _check_constraints(self, weights: Dict[str, float]) -> bool:
        """Check if weights satisfy constraints."""
        long_only = self._constraints.get("long_only", True)
        min_w = self._constraints.get("min_weight", 0.0)
        max_w = self._constraints.get("max_weight", 1.0)
        fully_invested = self._constraints.get("fully_invested", True)

        for asset, w in weights.items():
            if long_only and w < -1e-6:
                return False
            if w < min_w - 1e-6 or w > max_w + 1e-6:
                return False

        if fully_invested:
            total = sum(weights.values())
            if abs(total - 1.0) > 0.01:
                return False

        return True
