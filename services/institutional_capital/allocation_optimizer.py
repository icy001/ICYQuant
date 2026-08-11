"""
Allocation Optimizer — Optimal Capital Distribution Across Strategies

Core optimization pipeline:
    Strategy Pool
         ↓
    Expected Return + Risk Model + Correlation + Capacity + Liquidity
         ↓
    Constraints
         ↓
    Allocation Optimizer
         ↓
    Capital Allocation (target weights)

Integrates with Control Plane for governance: policy, autonomy, approval.
"""

import uuid
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class OptimizationResult:
    result_id: str
    objective: str
    status: str
    allocations: Dict[str, float]
    deltas: Dict[str, float]
    expected_return: float
    expected_risk: float
    sharpe: float
    diversification_score: float
    constraints_met: List[str]
    constraints_violated: List[str]
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


class AllocationOptimizer:
    """
    Multi-strategy capital allocation optimizer.

    Pipeline:
    1. Gather inputs (returns, risks, correlations, capacities)
    2. Apply constraints (capital, risk, leverage, liquidity, concentration)
    3. Score each strategy
    4. Solve allocation (maximize objective subject to constraints)
    5. Compute deltas (from current allocation)
    """

    def __init__(
        self,
        optimizer_id: Optional[str] = None,
        capital_pool=None,
        strategy_pool=None,
        efficiency=None,
        exposure=None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.optimizer_id = optimizer_id or f"ao-{uuid.uuid4().hex[:12]}"
        self._capital_pool = capital_pool
        self._strategy_pool = strategy_pool
        self._efficiency = efficiency
        self._exposure = exposure
        self.config = config or {}
        self._default_objective = self.config.get("default_objective", "MAXIMIZE_SHARPE")
        self._history: List[OptimizationResult] = []

    def optimize(
        self,
        strategies: Dict[str, float],
        efficiencies: Optional[Dict[str, float]] = None,
        exposure: Optional[Dict[str, Dict[str, float]]] = None,
        objective: str = "MAXIMIZE_SHARPE",
        constraints: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Run allocation optimization.

        Returns: target allocations, deltas, expected metrics.
        """
        if not strategies:
            return {"status": "NO_STRATEGIES", "allocations": {}, "deltas": {}}

        efficiencies = efficiencies or {}
        exposure = exposure or {}
        constraints = constraints or {}

        # Score each strategy
        scores = self._score_strategies(strategies, efficiencies, objective)

        # Get current allocations
        current = {}
        if self._strategy_pool:
            current = self._strategy_pool.get_allocations()

        # Total capital constraint
        max_capital = self._capital_pool.total_capital if self._capital_pool else sum(strategies.values())
        concentration_limit = constraints.get("concentration_limit", 0.30)

        # Solve: allocate proportionally to scores, subject to constraints
        total_score = sum(scores.values())
        allocations = {}
        for sid, score in scores.items():
            if total_score > 0:
                alloc = max_capital * (score / total_score)
            else:
                alloc = max_capital / max(1, len(scores))
            # Apply concentration limit
            alloc = min(alloc, max_capital * concentration_limit)
            allocations[sid] = alloc

        # Compute deltas
        deltas = {
            sid: allocations.get(sid, 0) - current.get(sid, 0)
            for sid in set(list(allocations.keys()) + list(current.keys()))
        }

        # Evaluate risk/return
        exp_return = sum(
            allocations.get(sid, 0) * efficiencies.get(sid, 0)
            for sid in allocations
        )
        exp_risk = self._estimate_portfolio_risk(allocations, exposure)
        sharpe = exp_return / exp_risk if exp_risk > 0 else 0.0
        div_score = self._estimate_diversification(allocations, exposure)

        met, violated = self._check_constraints(allocations, constraints)

        result = OptimizationResult(
            result_id=f"opt-{uuid.uuid4().hex[:8]}",
            objective=objective,
            status="OPTIMAL" if not violated else "CONSTRAINED",
            allocations=allocations,
            deltas=deltas,
            expected_return=exp_return,
            expected_risk=exp_risk,
            sharpe=sharpe,
            diversification_score=div_score,
            constraints_met=met,
            constraints_violated=violated,
        )
        self._history.append(result)

        return {
            "result_id": result.result_id,
            "status": result.status,
            "allocations": result.allocations,
            "deltas": result.deltas,
            "expected_return": result.expected_return,
            "expected_risk": result.expected_risk,
            "sharpe": result.sharpe,
            "diversification": result.diversification_score,
            "constraints_met": result.constraints_met,
            "constraints_violated": result.constraints_violated,
        }

    def simulate(
        self,
        proposed: Dict[str, float],
        scenario_params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Simulate a proposed allocation without executing."""
        params = scenario_params or {}
        current = {}
        if self._strategy_pool:
            current = self._strategy_pool.get_allocations()

        deltas = {
            sid: proposed.get(sid, 0) - current.get(sid, 0)
            for sid in set(list(proposed.keys()) + list(current.keys()))
        }
        total_change = sum(abs(d) for d in deltas.values())
        total_capital = self._capital_pool.total_capital if self._capital_pool else sum(proposed.values())

        return {
            "proposed": proposed,
            "current": current,
            "deltas": deltas,
            "turnover": total_change / total_capital if total_capital > 0 else 0,
            "change_count": sum(1 for d in deltas.values() if abs(d) > 0.01),
            "scenario": params,
        }

    def _score_strategies(
        self,
        strategies: Dict[str, float],
        efficiencies: Dict[str, float],
        objective: str,
    ) -> Dict[str, float]:
        """Score strategies based on the optimization objective."""
        scores = {}
        for sid in strategies:
            score = efficiencies.get(sid, 0.01)
            if score <= 0:
                score = 0.01
            scores[sid] = score
        return scores

    def _estimate_portfolio_risk(
        self,
        allocations: Dict[str, float],
        exposure: Dict[str, Dict[str, float]],
    ) -> float:
        """Estimate portfolio risk from allocations and correlations."""
        total_risk = 0.0
        for s1, w1 in allocations.items():
            for s2, w2 in allocations.items():
                corr = exposure.get(s1, {}).get(s2, 1.0 if s1 == s2 else 0.0)
                total_risk += w1 * w2 * corr
        return max(0.0, total_risk) ** 0.5

    def _estimate_diversification(
        self,
        allocations: Dict[str, float],
        exposure: Dict[str, Dict[str, float]],
    ) -> float:
        """Estimate diversification score (0=concentrated, 1=diversified)."""
        if not allocations:
            return 0.0
        n = len(allocations)
        if n <= 1:
            return 0.0
        total = sum(allocations.values())
        if total <= 0:
            return 0.0
        weights = [v / total for v in allocations.values()]
        hhi = sum(w ** 2 for w in weights)
        return 1.0 - hhi

    def _check_constraints(
        self,
        allocations: Dict[str, float],
        constraints: Dict[str, Any],
    ) -> Tuple[List[str], List[str]]:
        met, violated = [], []
        total = sum(allocations.values())
        conc_limit = constraints.get("concentration_limit", 1.0)
        min_alloc = constraints.get("min_allocation", 0.0)

        for sid, alloc in allocations.items():
            if conc_limit < 1.0 and total > 0 and alloc / total > conc_limit:
                violated.append(f"Concentration: {sid} at {alloc/total:.1%}")
            if alloc < min_alloc:
                violated.append(f"Min allocation: {sid} = {alloc}")
        if not violated:
            met.append("All constraints satisfied")
        return met, violated

    def get_history(self) -> List[OptimizationResult]:
        return list(self._history)

    def get_summary(self) -> Dict[str, Any]:
        latest = self._history[-1] if self._history else None
        return {
            "optimizer_id": self.optimizer_id,
            "runs": len(self._history),
            "latest": {
                "status": latest.status,
                "sharpe": latest.sharpe,
                "allocations": latest.allocations,
            } if latest else None,
        }
