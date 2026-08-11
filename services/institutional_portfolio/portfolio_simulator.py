"""
Portfolio Simulator — Pre-Rebalance Simulation

Before executing large rebalances, simulate:
    Current Portfolio → Proposed Portfolio → Risk/Return/Cost

Only proposals that pass the Portfolio Guard proceed to execution.
"""

import uuid
import logging
from typing import Dict, Optional, Any
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class SimulationStatus(str, Enum):
    PASSED = "PASSED"
    FAILED = "FAILED"
    NEEDS_REVIEW = "NEEDS_REVIEW"


@dataclass
class SimulationResult:
    simulation_id: str
    status: SimulationStatus = SimulationStatus.NEEDS_REVIEW
    current_risk: float = 0.0
    proposed_risk: float = 0.0
    risk_change: float = 0.0
    expected_return: float = 0.0
    expected_cost: float = 0.0
    net_benefit: float = 0.0
    violations: list = field(default_factory=list)


class PortfolioSimulator:
    """
    Simulates proposed portfolio changes before execution.

    Pipeline:
    1. Compute current portfolio metrics
    2. Apply proposed changes
    3. Compute new metrics
    4. Compare risk/return/cost
    5. Validate against guard constraints
    """

    def __init__(
        self,
        simulator_id: Optional[str] = None,
        guard=None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.simulator_id = simulator_id or f"psim-{uuid.uuid4().hex[:12]}"
        self._guard = guard
        self.config = config or {}
        self._results: list = []

    def simulate(
        self,
        current_weights: Dict[str, float],
        proposed_weights: Dict[str, float],
        expected_returns: Optional[Dict[str, float]] = None,
    ) -> SimulationResult:
        """Simulate portfolio transition from current to proposed weights."""
        expected_returns = expected_returns or {}
        result = SimulationResult(
            simulation_id=f"sim-{uuid.uuid4().hex[:8]}",
        )

        # Risk estimates
        result.current_risk = sum(abs(w) for w in current_weights.values()) * 0.15
        result.proposed_risk = sum(abs(w) for w in proposed_weights.values()) * 0.15
        result.risk_change = result.proposed_risk - result.current_risk

        # Return estimate
        result.expected_return = sum(
            proposed_weights.get(a, 0) * expected_returns.get(a, 0)
            for a in set(list(proposed_weights.keys()))
        )

        # Cost estimate
        result.expected_cost = sum(
            abs(proposed_weights.get(a, 0) - current_weights.get(a, 0))
            for a in set(list(current_weights.keys()) + list(proposed_weights.keys()))
        ) * 0.0005

        result.net_benefit = result.expected_return - result.expected_cost

        # Guard check
        if self._guard:
            guard_result = self._guard.check({
                "risk_change": result.risk_change,
                "net_benefit": result.net_benefit,
            })
            if guard_result.get("allowed"):
                result.status = SimulationStatus.PASSED
            else:
                result.status = SimulationStatus.FAILED
                result.violations = guard_result.get("reasons", [])
        else:
            result.status = SimulationStatus.PASSED if result.net_benefit > 0 else SimulationStatus.NEEDS_REVIEW

        self._results.append(result)
        return result
