"""Capital Allocation Solver — constraint-satisfaction solver for allocations.

Ensures all allocation plans satisfy the complete constraint set:
Capital, Risk, Capacity, Liquidity, Concentration, Stress, Survival.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class SolutionStatus(str, Enum):
    """Solver solution status."""
    FEASIBLE = "FEASIBLE"
    OPTIMAL = "OPTIMAL"
    INFEASIBLE = "INFEASIBLE"
    PARTIALLY_FEASIBLE = "PARTIALLY_FEASIBLE"
    CONSTRAINT_VIOLATED = "CONSTRAINT_VIOLATED"
    TIMEOUT = "TIMEOUT"


@dataclass
class SolverConstraint:
    """A single constraint for the solver."""
    name: str
    check_fn: callable
    violation_message: str = ""
    priority: int = 0
    is_hard: bool = True

    def check(self, solution: Dict[str, float]) -> Tuple[bool, str]:
        try:
            return self.check_fn(solution), self.violation_message
        except Exception as e:
            return False, f"Constraint [{self.name}] error: {e}"


@dataclass
class SolverResult:
    """Result of a constraint satisfaction solve."""
    status: SolutionStatus = SolutionStatus.FEASIBLE
    solution: Dict[str, float] = field(default_factory=dict)
    objective_value: float = 0.0
    satisfied_constraints: List[str] = field(default_factory=list)
    violated_constraints: List[str] = field(default_factory=list)
    violations_detail: Dict[str, str] = field(default_factory=dict)
    iterations: int = 0
    runtime_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)


class CapitalAllocationSolver:
    """Constraint satisfaction solver for capital allocation.

    Takes a candidate allocation and ensures it satisfies all
    hard and soft constraints, applying repairs when possible.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self._config = config or {}
        self._max_iterations = self._config.get("max_iterations", 200)
        self._constraints: List[SolverConstraint] = []
        self._repair_strategies: Dict[str, callable] = {}

    def add_constraint(self, name: str, check_fn: callable,
                       violation_message: str = "",
                       priority: int = 0, is_hard: bool = True) -> None:
        """Add a constraint to the solver."""
        self._constraints.append(SolverConstraint(
            name=name,
            check_fn=check_fn,
            violation_message=violation_message,
            priority=priority,
            is_hard=is_hard,
        ))
        self._constraints.sort(key=lambda c: c.priority, reverse=True)

    def register_repair(self, constraint_name: str, repair_fn: callable) -> None:
        """Register a repair strategy for a constraint."""
        self._repair_strategies[constraint_name] = repair_fn

    def solve(self, candidate: Dict[str, float],
              deployable_capital: float) -> SolverResult:
        """Solve the constraint satisfaction for a candidate allocation.

        Iteratively checks and repairs until feasible or max iterations.
        """
        import time
        start_time = time.time()

        result = SolverResult(solution=dict(candidate))

        if not candidate or deployable_capital <= 0:
            result.status = SolutionStatus.INFEASIBLE
            return result

        current = dict(candidate)

        for iteration in range(self._max_iterations):
            all_satisfied = True
            result.satisfied_constraints = []
            result.violated_constraints = []
            result.violations_detail = {}

            for constraint in self._constraints:
                satisfied, msg = constraint.check(current)
                if satisfied:
                    result.satisfied_constraints.append(constraint.name)
                else:
                    all_satisfied = False
                    result.violated_constraints.append(constraint.name)
                    result.violations_detail[constraint.name] = msg

                    # Attempt repair
                    repair_fn = self._repair_strategies.get(constraint.name)
                    if repair_fn and constraint.is_hard:
                        try:
                            current = repair_fn(current, deployable_capital)
                        except Exception:
                            pass

            if all_satisfied:
                result.status = SolutionStatus.FEASIBLE
                result.solution = current
                result.iterations = iteration + 1
                result.runtime_ms = (time.time() - start_time) * 1000
                return result

        # Partial feasibility
        hard_violations = [
            c for c in self._constraints
            if c.is_hard and c.name in result.violated_constraints
        ]
        if hard_violations:
            result.status = SolutionStatus.INFEASIBLE
        else:
            result.status = SolutionStatus.PARTIALLY_FEASIBLE

        result.solution = current
        result.iterations = self._max_iterations
        result.runtime_ms = (time.time() - start_time) * 1000
        return result

    def check_feasibility(self, solution: Dict[str, float]) -> List[str]:
        """Quick feasibility check — returns list of violated constraint names."""
        violations = []
        for constraint in self._constraints:
            satisfied, _ = constraint.check(solution)
            if not satisfied:
                violations.append(constraint.name)
        return violations

    def is_feasible(self, solution: Dict[str, float]) -> bool:
        """Quick check if solution satisfies all constraints."""
        return len(self.check_feasibility(solution)) == 0

    # Common repair strategies
    @staticmethod
    def repair_capital_limit(weights: Dict[str, float],
                             deployable: float) -> Dict[str, float]:
        """Repair: scale weights to fit within deployable capital."""
        total = sum(weights.values())
        if total <= deployable or total <= 0:
            return weights
        scale = deployable / total
        return {k: v * scale for k, v in weights.items()}

    @staticmethod
    def repair_non_negative(weights: Dict[str, float],
                            deployable: float) -> Dict[str, float]:
        """Repair: ensure all weights are non-negative."""
        cleaned = {k: max(0.0, v) for k, v in weights.items()}
        return CapitalAllocationSolver.repair_capital_limit(cleaned, deployable)

    @staticmethod
    def repair_concentration(weights: Dict[str, float],
                             deployable: float,
                             max_single: float = 0.35) -> Dict[str, float]:
        """Repair: clip individual weights to max concentration."""
        capped = {}
        for k, v in weights.items():
            capped[k] = min(v, deployable * max_single)
        return CapitalAllocationSolver.repair_capital_limit(capped, deployable)

    @staticmethod
    def repair_capacity(weights: Dict[str, float],
                        deployable: float,
                        capacities: Dict[str, float]) -> Dict[str, float]:
        """Repair: clip weights to individual strategy capacities."""
        capped = {}
        for k, v in weights.items():
            cap = capacities.get(k, float("inf"))
            capped[k] = min(v, cap)
        return CapitalAllocationSolver.repair_capital_limit(capped, deployable)
