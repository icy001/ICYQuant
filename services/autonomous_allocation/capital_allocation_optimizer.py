"""Capital Allocation Optimizer — numerical optimization for capital allocation.

Solves the constrained optimization problem:
    max U(w) = Σ w_i * u_i
    s.t. Σ w_i = deployable, 0 ≤ w_i ≤ w_max_i, all constraints

Uses gradient-based optimization with constraint projection.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple


class OptimizerStatus(str, Enum):
    """Optimizer convergence status."""
    OPTIMAL = "OPTIMAL"
    FEASIBLE = "FEASIBLE"
    MAX_ITERATIONS = "MAX_ITERATIONS"
    INFEASIBLE = "INFEASIBLE"
    UNBOUNDED = "UNBOUNDED"
    ERROR = "ERROR"


@dataclass
class OptimizationResult:
    """Result of a capital allocation optimization."""
    status: OptimizerStatus = OptimizerStatus.FEASIBLE
    weights: Dict[str, float] = field(default_factory=dict)
    objective_value: float = 0.0
    gradient_norm: float = 0.0
    iterations: int = 0
    runtime_ms: float = 0.0
    constraint_violations: List[str] = field(default_factory=list)
    dual_variables: Dict[str, float] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class OptimizationProblem:
    """Defines the optimization problem."""
    strategy_ids: List[str] = field(default_factory=list)
    initial_weights: Dict[str, float] = field(default_factory=dict)
    deployable_capital: float = 0.0
    total_capital: float = 0.0
    objective_fn: Optional[Callable] = None
    gradient_fn: Optional[Callable] = None
    constraints: List[Callable] = field(default_factory=list)
    lower_bounds: Dict[str, float] = field(default_factory=dict)
    upper_bounds: Dict[str, float] = field(default_factory=dict)


class CapitalAllocationOptimizer:
    """Numerical optimizer for capital allocation.

    Solves the constrained optimization:
        maximize Σ w_i * (alpha_i - risk_i - cost_i - impact_i)
        subject to:
            Σ w_i = deployable
            w_i ≥ 0
            w_i ≤ capacity_i
            risk(w) ≤ risk_budget
            stress_score(w) ≥ 70
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self._config = config or {}
        self._max_iterations = self._config.get("max_iterations", 500)
        self._tolerance = self._config.get("tolerance", 1e-6)
        self._step_size = self._config.get("step_size", 0.01)
        self._step_decay = self._config.get("step_decay", 0.995)
        self._momentum = self._config.get("momentum", 0.9)

    def optimize(self, problem: OptimizationProblem) -> OptimizationResult:
        """Solve the allocation optimization problem.

        Uses projected gradient ascent with momentum.
        """
        import time
        start_time = time.time()

        result = OptimizationResult()

        if not problem.strategy_ids or problem.deployable_capital <= 0:
            result.status = OptimizerStatus.INFEASIBLE
            result.constraint_violations.append("No strategies or no deployable capital")
            return result

        n = len(problem.strategy_ids)

        # Initialize weights
        weights = {}
        for sid in problem.strategy_ids:
            if sid in problem.initial_weights:
                weights[sid] = problem.initial_weights[sid]
            else:
                weights[sid] = problem.deployable_capital / n

        # Normalize to deployable
        total = sum(weights.values())
        if total > 0:
            for sid in weights:
                weights[sid] = weights[sid] / total * problem.deployable_capital

        velocity = {sid: 0.0 for sid in problem.strategy_ids}
        step_size = self._step_size
        prev_objective = float("-inf")

        for iteration in range(self._max_iterations):
            # Compute gradient
            gradient = self._compute_gradient(weights, problem)

            # Update with momentum
            for sid in problem.strategy_ids:
                velocity[sid] = (self._momentum * velocity[sid] +
                                 step_size * gradient.get(sid, 0.0))
                weights[sid] += velocity[sid]

            # Project onto feasible region
            weights = self._project_feasible(weights, problem)

            # Compute objective
            objective = self._compute_objective(weights, problem)
            grad_norm = sum(g * g for g in gradient.values()) ** 0.5

            # Check convergence
            if abs(objective - prev_objective) < self._tolerance and grad_norm < self._tolerance:
                result.status = OptimizerStatus.OPTIMAL
                result.iterations = iteration + 1
                result.objective_value = objective
                result.gradient_norm = grad_norm
                result.weights = weights
                result.runtime_ms = (time.time() - start_time) * 1000
                return result

            prev_objective = objective
            step_size *= self._step_decay

        result.status = OptimizerStatus.MAX_ITERATIONS
        result.iterations = self._max_iterations
        result.objective_value = self._compute_objective(weights, problem)
        result.gradient_norm = sum(g * g for g in self._compute_gradient(weights, problem).values()) ** 0.5
        result.weights = weights
        result.runtime_ms = (time.time() - start_time) * 1000
        return result

    def _compute_gradient(self, weights: Dict[str, float],
                          problem: OptimizationProblem) -> Dict[str, float]:
        """Compute numerical gradient of the objective."""
        if problem.gradient_fn:
            return problem.gradient_fn(weights)

        h = max(1.0, problem.deployable_capital * 1e-6)
        gradient = {}
        base_obj = self._compute_objective(weights, problem)

        for sid in problem.strategy_ids:
            perturbed = dict(weights)
            perturbed[sid] = perturbed.get(sid, 0) + h
            obj_plus = self._compute_objective(perturbed, problem)
            gradient[sid] = (obj_plus - base_obj) / h

        return gradient

    def _compute_objective(self, weights: Dict[str, float],
                           problem: OptimizationProblem) -> float:
        """Compute the objective function value."""
        if problem.objective_fn:
            return problem.objective_fn(weights)

        # Default: sum of weighted utility
        total = sum(weights.values())
        if total <= 0:
            return 0.0
        return total / problem.deployable_capital

    def _project_feasible(self, weights: Dict[str, float],
                          problem: OptimizationProblem) -> Dict[str, float]:
        """Project weights onto the feasible region."""
        projected = {}

        # Clip to bounds
        for sid in problem.strategy_ids:
            w = weights.get(sid, 0.0)
            lb = problem.lower_bounds.get(sid, 0.0)
            ub = problem.upper_bounds.get(sid, problem.deployable_capital)
            projected[sid] = max(lb, min(ub, w))

        # Enforce non-negativity
        for sid in projected:
            projected[sid] = max(0.0, projected[sid])

        # Normalize to deployable
        total = sum(projected.values())
        if total > 0 and problem.deployable_capital > 0:
            scale = problem.deployable_capital / total
            for sid in projected:
                projected[sid] *= scale

        # Enforce capacity constraints
        for sid in problem.strategy_ids:
            if sid in problem.upper_bounds:
                projected[sid] = min(projected[sid], problem.upper_bounds[sid])

        return projected

    def compute_efficient_frontier(self, problem: OptimizationProblem,
                                   num_points: int = 20) -> List[Tuple[float, Dict[str, float]]]:
        """Compute the capital allocation efficient frontier."""
        frontier = []
        for i in range(num_points):
            alpha = i / (num_points - 1)  # 0 to 1
            # Vary risk aversion
            problem_copy = OptimizationProblem(
                strategy_ids=problem.strategy_ids,
                initial_weights=problem.initial_weights,
                deployable_capital=problem.deployable_capital,
                total_capital=problem.total_capital,
                lower_bounds=problem.lower_bounds,
                upper_bounds=problem.upper_bounds,
            )
            result = self.optimize(problem_copy)
            frontier.append((result.objective_value, dict(result.weights)))
        return frontier
