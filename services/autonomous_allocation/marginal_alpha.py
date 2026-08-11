"""Marginal Alpha — computes marginal alpha for incremental capital.

Marginal alpha answers: "If I add $1M more, how much additional
return do I get?"

As capital increases, marginal alpha typically decays due to:
- Alpha capacity saturation
- Market impact growth
- Signal dilution
- Competition for the same alpha sources
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class MarginalAlphaResult:
    """Marginal alpha analysis result."""
    strategy_id: str
    base_alpha: float = 0.0
    marginal_alpha: float = 0.0
    current_capital: float = 0.0
    alpha_per_million: float = 0.0  # alpha per $1M incremental
    decay_rate: float = 0.0
    optimal_capital: float = 0.0
    alpha_efficiency: float = 0.0  # marginal / base
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def summarize(self) -> str:
        return (
            f"MarginalAlpha[{self.strategy_id}] marginal={self.marginal_alpha:.4f} "
            f"base={self.base_alpha:.4f} per_1M={self.alpha_per_million:.6f} "
            f"efficiency={self.alpha_efficiency:.2%}"
        )


class MarginalAlpha:
    """Computes marginal alpha for capital allocation decisions.

    Models alpha decay: Return = BaseReturn * (BaseCapital / Capital)^decay
    Marginal Alpha = d(Return * Capital) / d(Capital)
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self._config = config or {}
        self._default_decay = self._config.get("default_decay_exponent", 0.3)
        self._epsilon = 1_000.0  # $1K increment for numerical derivative

    def compute(self, strategy_id: str,
                base_capital: float,
                base_return: float,
                current_capital: float,
                decay_exponent: Optional[float] = None) -> MarginalAlphaResult:
        """Compute marginal alpha using power-law alpha decay model.

        Return = BaseReturn * (BaseCapital / Capital)^decay
        TotalReturn = Capital * Return = BaseReturn * BaseCapital^decay * Capital^(1-decay)
        MarginalAlpha = d(TotalReturn)/d(Capital) = BaseReturn * (1-decay) * (BaseCapital/Capital)^decay
        """
        decay = decay_exponent if decay_exponent is not None else self._default_decay

        if current_capital <= 0 or base_capital <= 0:
            return MarginalAlphaResult(
                strategy_id=strategy_id,
                base_alpha=base_return,
                marginal_alpha=base_return,
                current_capital=current_capital,
            )

        # Base alpha (total return rate at current capital)
        capital_ratio = base_capital / current_capital
        base_alpha = base_return * (capital_ratio ** decay)

        # Marginal alpha
        marginal_alpha = base_return * (1.0 - decay) * (capital_ratio ** decay)

        # Alpha per $1M
        alpha_per_million = marginal_alpha * 1_000_000.0 / current_capital if current_capital > 0 else 0.0

        # Alpha efficiency ratio
        alpha_efficiency = marginal_alpha / base_alpha if base_alpha > 0 else 1.0

        # Optimal capital: where marginal alpha = marginal cost threshold
        min_threshold = self._config.get("min_marginal_alpha", 0.02)
        if min_threshold > 0 and marginal_alpha > 0:
            optimal_capital = base_capital * (
                base_return * (1.0 - decay) / min_threshold
            ) ** (1.0 / decay)
        else:
            optimal_capital = current_capital

        return MarginalAlphaResult(
            strategy_id=strategy_id,
            base_alpha=base_alpha,
            marginal_alpha=marginal_alpha,
            current_capital=current_capital,
            alpha_per_million=alpha_per_million,
            decay_rate=decay,
            optimal_capital=optimal_capital,
            alpha_efficiency=alpha_efficiency,
        )

    def compute_numerical(self, strategy_id: str,
                          capital_levels: List[float],
                          returns: List[float],
                          current_capital: float) -> MarginalAlphaResult:
        """Compute marginal alpha numerically from capital-return data points."""
        if len(capital_levels) < 2 or current_capital <= 0:
            return MarginalAlphaResult(
                strategy_id=strategy_id,
                current_capital=current_capital,
            )

        # Fit power-law decay
        import math
        log_capital = [math.log(c) for c in capital_levels]
        log_return = [math.log(max(1e-6, r)) for r in returns]
        n = len(log_capital)

        # Linear regression in log-log space
        sum_x = sum(log_capital)
        sum_y = sum(log_return)
        sum_xy = sum(x * y for x, y in zip(log_capital, log_return))
        sum_x2 = sum(x * x for x in log_capital)

        slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x * sum_x)
        intercept = (sum_y - slope * sum_x) / n

        decay = -slope
        base_return = math.exp(intercept)

        # Interpolate return at current capital
        log_curr = math.log(current_capital)
        current_return = math.exp(intercept + slope * log_curr)
        marginal = current_return * (1.0 - decay) if decay < 1.0 else 0.0

        return MarginalAlphaResult(
            strategy_id=strategy_id,
            base_alpha=current_return,
            marginal_alpha=marginal,
            current_capital=current_capital,
            alpha_per_million=marginal * 1_000_000.0 / current_capital,
            decay_rate=max(0.0, decay),
        )

    def should_add_capital(self, result: MarginalAlphaResult,
                           marginal_cost: float = 0.0,
                           marginal_risk: float = 0.0) -> Tuple[bool, str]:
        """Determine if more capital should be added.

        Stop adding when: MarginalAlpha < MarginalCost + MarginalRisk
        """
        threshold = marginal_cost + marginal_risk
        if result.marginal_alpha > threshold:
            return True, (
                f"Marginal alpha ({result.marginal_alpha:.4f}) > "
                f"threshold ({threshold:.4f})"
            )
        return False, (
            f"Marginal alpha ({result.marginal_alpha:.4f}) ≤ "
            f"threshold ({threshold:.4f}), stop adding capital"
        )
