"""
Allocation Simulator — Simulate capital allocation changes before execution.

Pipeline:
    Current Allocation → Proposed Allocation → Scenario Simulation → Risk/Return/Drawdown

Avoids changing production capital without prior validation.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple


class SimulationStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    WARNING = "warning"


@dataclass
class AllocationState:
    """Current or proposed allocation state snapshot."""

    strategy_id: str = ""
    capital: float = 0.0
    weight: float = 0.0
    expected_return: float = 0.0
    volatility: float = 0.0
    sharpe: float = 0.0
    max_drawdown: float = 0.0
    correlation_to_portfolio: float = 0.0
    capital_efficiency: float = 0.0
    capacity_utilization: float = 0.0

    def to_dict(self) -> Dict[str, float]:
        return {
            "capital": self.capital,
            "weight": self.weight,
            "expected_return": self.expected_return,
            "volatility": self.volatility,
            "sharpe": self.sharpe,
            "max_drawdown": self.max_drawdown,
            "correlation_to_portfolio": self.correlation_to_portfolio,
            "capital_efficiency": self.capital_efficiency,
            "capacity_utilization": self.capacity_utilization,
        }


@dataclass
class SimulationConfig:
    """Configuration for a simulation run."""

    monte_carlo_samples: int = 1000
    volatility_shock: float = 0.0        # additive: sigma *= (1+shock)
    correlation_shock: float = 0.0        # additive to correlations
    liquidity_shock: float = 0.0          # multiplicative on liquidity
    execution_cost_factor: float = 1.0    # multiplier on expected costs
    drawdown_threshold: float = 0.15      # trigger warning beyond this
    risk_threshold: float = 0.20          # trigger failure beyond this


@dataclass
class SimulationResult:
    """Result of simulating an allocation change."""

    simulation_id: str = field(default_factory=lambda: f"SIM-{uuid.uuid4().hex[:8]}")
    status: SimulationStatus = SimulationStatus.PENDING

    # Pre and post states
    current_portfolio: Dict[str, AllocationState] = field(default_factory=dict)
    proposed_portfolio: Dict[str, AllocationState] = field(default_factory=dict)

    # Aggregate metrics
    current_total_return: float = 0.0
    proposed_total_return: float = 0.0
    return_improvement: float = 0.0

    current_portfolio_risk: float = 0.0
    proposed_portfolio_risk: float = 0.0
    risk_change: float = 0.0

    current_max_drawdown: float = 0.0
    proposed_max_drawdown: float = 0.0

    current_capital_efficiency: float = 0.0
    proposed_capital_efficiency: float = 0.0

    estimated_execution_cost: float = 0.0
    net_benefit: float = 0.0             # return_improvement - execution_cost

    monte_carlo_results: List[Dict[str, float]] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "simulation_id": self.simulation_id,
            "status": self.status.value,
            "return_improvement": self.return_improvement,
            "risk_change": self.risk_change,
            "current_portfolio_risk": self.current_portfolio_risk,
            "proposed_portfolio_risk": self.proposed_portfolio_risk,
            "current_max_drawdown": self.current_max_drawdown,
            "proposed_max_drawdown": self.proposed_max_drawdown,
            "current_capital_efficiency": self.current_capital_efficiency,
            "proposed_capital_efficiency": self.proposed_capital_efficiency,
            "estimated_execution_cost": self.estimated_execution_cost,
            "net_benefit": self.net_benefit,
            "warnings": self.warnings,
            "errors": self.errors,
        }


class AllocationSimulator:
    """Simulates allocation changes and evaluates risk/return impact."""

    def __init__(self, config: Optional[SimulationConfig] = None):
        self.config = config or SimulationConfig()
        self._history: List[SimulationResult] = []

    def simulate(
        self,
        current: Dict[str, AllocationState],
        proposed: Dict[str, AllocationState],
        total_capital: float = 0.0,
    ) -> SimulationResult:
        """Simulate a capital allocation change from current to proposed."""
        result = SimulationResult(
            current_portfolio=dict(current),
            proposed_portfolio=dict(proposed),
        )

        # Aggregate metrics — current
        current_metrics = self._aggregate(current)
        proposed_metrics = self._aggregate(proposed)

        result.current_total_return = current_metrics["total_return"]
        result.proposed_total_return = proposed_metrics["total_return"]
        result.return_improvement = result.proposed_total_return - result.current_total_return

        result.current_portfolio_risk = current_metrics["portfolio_risk"]
        result.proposed_portfolio_risk = proposed_metrics["portfolio_risk"]
        result.risk_change = result.proposed_portfolio_risk - result.current_portfolio_risk

        result.current_max_drawdown = current_metrics["max_drawdown"]
        result.proposed_max_drawdown = proposed_metrics["max_drawdown"]

        result.current_capital_efficiency = current_metrics["capital_efficiency"]
        result.proposed_capital_efficiency = proposed_metrics["capital_efficiency"]

        # Execution cost estimate
        delta_capital = sum(
            abs(proposed.get(sid, AllocationState()).capital - current.get(sid, AllocationState()).capital)
            for sid in set(list(current.keys()) + list(proposed.keys()))
        )
        result.estimated_execution_cost = delta_capital * 0.001 * self.config.execution_cost_factor

        result.net_benefit = result.return_improvement - result.estimated_execution_cost

        # Monte Carlo simulation
        if self.config.monte_carlo_samples > 0:
            result.monte_carlo_results = self._monte_carlo(current_metrics, proposed_metrics)

        # Risk checks
        if result.proposed_portfolio_risk > self.config.risk_threshold:
            result.errors.append(f"Proposed risk {result.proposed_portfolio_risk:.3f} exceeds threshold {self.config.risk_threshold}")
            result.status = SimulationStatus.FAILED

        if result.proposed_max_drawdown > self.config.drawdown_threshold:
            result.warnings.append(f"Proposed max drawdown {result.proposed_max_drawdown:.3f} exceeds threshold {self.config.drawdown_threshold}")
            if result.status != SimulationStatus.FAILED:
                result.status = SimulationStatus.WARNING

        if result.net_benefit < 0:
            result.warnings.append(f"Net benefit is negative: {result.net_benefit:.4f}")

        if result.status == SimulationStatus.PENDING:
            result.status = SimulationStatus.PASSED

        self._history.append(result)
        return result

    def _aggregate(self, portfolio: Dict[str, AllocationState]) -> Dict[str, float]:
        """Aggregate portfolio-level metrics from individual strategy states."""
        if not portfolio:
            return {
                "total_return": 0.0, "portfolio_risk": 0.0,
                "max_drawdown": 0.0, "capital_efficiency": 0.0,
            }

        total_capital = sum(s.capital for s in portfolio.values())
        if total_capital == 0:
            return {
                "total_return": 0.0, "portfolio_risk": 0.0,
                "max_drawdown": 0.0, "capital_efficiency": 0.0,
            }

        total_return = sum(s.capital * s.expected_return for s in portfolio.values()) / total_capital

        # Simplified risk aggregation
        weights = [s.capital / total_capital for s in portfolio.values()]
        vols = [s.volatility for s in portfolio.values()]
        portfolio_risk = sum(w * v for w, v in zip(weights, vols))

        max_drawdown = max((s.max_drawdown for s in portfolio.values()), default=0.0)
        total_eff = sum(s.capital_efficiency for s in portfolio.values()) / len(portfolio)

        return {
            "total_return": total_return,
            "portfolio_risk": portfolio_risk,
            "max_drawdown": max_drawdown,
            "capital_efficiency": total_eff,
        }

    def _monte_carlo(self, current: Dict[str, float], proposed: Dict[str, float]) -> List[Dict[str, float]]:
        """Run Monte Carlo simulations of return and risk outcomes."""
        results = []
        import random
        for _ in range(min(self.config.monte_carlo_samples, 100)):
            shock = random.gauss(0, proposed.get("portfolio_risk", 0.05))
            sim_return = proposed.get("total_return", 0) + shock
            sim_risk = abs(proposed.get("portfolio_risk", 0) * (1 + random.gauss(0, 0.1)))
            results.append({
                "simulated_return": sim_return,
                "simulated_risk": sim_risk,
                "simulated_sharpe": sim_return / max(sim_risk, 1e-6),
            })
        return results

    def history(self) -> List[SimulationResult]:
        return list(self._history)
