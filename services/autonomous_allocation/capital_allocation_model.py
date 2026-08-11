"""Capital Allocation Model — mathematical model for optimal capital distribution.

Models the relationship between capital deployed and expected return,
incorporating alpha decay, capacity constraints, and risk scaling.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class ModelType(str, Enum):
    """Type of capital allocation model."""
    LINEAR = "LINEAR"
    QUADRATIC = "QUADRATIC"
    LOGARITHMIC = "LOGARITHMIC"
    POWER_LAW = "POWER_LAW"
    KELLY_FRACTIONAL = "KELLY_FRACTIONAL"


@dataclass
class CapitalResponseCurve:
    """Models how expected return responds to capital deployment.

    Typically exhibits diminishing marginal returns:
    Return = BaseReturn * (BaseCapital / Capital)^decay_exponent
    """
    strategy_id: str
    base_capital: float = 1_000_000.0
    base_return: float = 0.10
    decay_exponent: float = 0.3
    model_type: ModelType = ModelType.POWER_LAW

    def expected_return(self, capital: float) -> float:
        """Compute expected return at a given capital level."""
        if capital <= 0:
            return 0.0
        if self.model_type == ModelType.POWER_LAW:
            return self.base_return * (self.base_capital / capital) ** self.decay_exponent
        elif self.model_type == ModelType.LOGARITHMIC:
            ratio = capital / self.base_capital
            if ratio <= 1:
                return self.base_return * ratio
            return self.base_return * (1 + self.decay_exponent * (ratio - 1) ** 0.5)
        elif self.model_type == ModelType.LINEAR:
            return self.base_return
        elif self.model_type == ModelType.QUADRATIC:
            ratio = capital / self.base_capital
            return self.base_return * (1 - 0.5 * self.decay_exponent * (ratio - 1) ** 2)
        elif self.model_type == ModelType.KELLY_FRACTIONAL:
            return self.base_return * (self.base_capital / capital)
        return self.base_return

    def marginal_return(self, capital: float) -> float:
        """Compute marginal return at a given capital level."""
        epsilon = max(1.0, capital * 1e-6)
        ret1 = self.expected_return(capital)
        ret2 = self.expected_return(capital + epsilon)
        return (ret2 - ret1) / epsilon

    def optimal_capital(self, min_return: float = 0.02) -> float:
        """Find capital level where marginal return drops below threshold."""
        low = self.base_capital
        high = self.base_capital * 100
        for _ in range(50):
            mid = (low + high) / 2
            if self.expected_return(mid) > min_return:
                low = mid
            else:
                high = mid
        return (low + high) / 2

    def capacity_utilization(self, capital: float, max_capacity: float) -> float:
        """Compute capacity utilization ratio."""
        if max_capacity <= 0:
            return 1.0
        return min(1.0, capital / max_capacity)


@dataclass
class CapitalAllocationModel:
    """Unified capital allocation model for a portfolio of strategies.

    Combines individual strategy response curves to optimize
    portfolio-level capital distribution.
    """
    timestamp: datetime = field(default_factory=datetime.utcnow)
    curves: Dict[str, CapitalResponseCurve] = field(default_factory=dict)
    total_capital: float = 0.0
    allocations: Dict[str, float] = field(default_factory=dict)

    def add_curve(self, curve: CapitalResponseCurve) -> None:
        """Add a strategy response curve."""
        self.curves[curve.strategy_id] = curve

    def get_curve(self, strategy_id: str) -> Optional[CapitalResponseCurve]:
        """Get a strategy's response curve."""
        return self.curves.get(strategy_id)

    def portfolio_expected_return(self) -> float:
        """Compute weighted portfolio expected return."""
        if self.total_capital <= 0:
            return 0.0
        total = 0.0
        for sid, capital in self.allocations.items():
            curve = self.curves.get(sid)
            if curve:
                total += capital * curve.expected_return(capital)
        return total / self.total_capital if self.total_capital > 0 else 0.0

    def marginal_portfolio_return(self, strategy_id: str) -> float:
        """Compute marginal portfolio return from adding to a strategy."""
        curve = self.curves.get(strategy_id)
        if not curve:
            return 0.0
        current = self.allocations.get(strategy_id, 0.0)
        return curve.marginal_return(current)

    def optimize_equal_weight(self) -> Dict[str, float]:
        """Equal-weight optimization."""
        n = len(self.curves)
        if n == 0:
            return {}
        per_strategy = self.total_capital / n
        return {sid: per_strategy for sid in self.curves}

    def optimize_marginal_equality(self, max_iterations: int = 200) -> Dict[str, float]:
        """Optimize so that marginal return is equalized across strategies.

        This is the theoretical optimum: dR/dC should be equal for all strategies.
        """
        if not self.curves or self.total_capital <= 0:
            return {}

        # Start with equal weight
        n = len(self.curves)
        per = self.total_capital / n
        alloc = {sid: per for sid in self.curves}

        for _ in range(max_iterations):
            marginals = {}
            for sid, curve in self.curves.items():
                marginals[sid] = curve.marginal_return(alloc[sid])

            avg_marginal = sum(marginals.values()) / len(marginals)
            max_dev = 0.0

            for sid in self.curves:
                diff = marginals[sid] - avg_marginal
                max_dev = max(max_dev, abs(diff))
                adjustment = diff * alloc[sid] * 0.1
                alloc[sid] = max(0, alloc[sid] + adjustment)

            # Renormalize
            total = sum(alloc.values())
            if total > 0:
                for sid in alloc:
                    alloc[sid] = alloc[sid] / total * self.total_capital

            if max_dev < 1e-6:
                break

        self.allocations = alloc
        return alloc

    def validate_allocations(self, max_weight: float = 0.50,
                             min_weight: float = 0.0) -> List[str]:
        """Validate that allocations respect portfolio constraints."""
        violations = []
        total = sum(self.allocations.values())

        if self.total_capital > 0:
            for sid, capital in self.allocations.items():
                weight = capital / self.total_capital
                if weight > max_weight:
                    violations.append(
                        f"Strategy {sid} weight {weight:.4f} exceeds max {max_weight:.4f}"
                    )
                if weight < min_weight and capital > 0:
                    violations.append(
                        f"Strategy {sid} weight {weight:.4f} below min {min_weight:.4f}"
                    )

        if abs(total - self.total_capital) > 0.01:
            violations.append(
                f"Total allocation {total:,.2f} != total capital {self.total_capital:,.2f}"
            )

        return violations
