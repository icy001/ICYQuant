"""Marginal Survival — computes marginal survival contribution for additional capital.

Marginal survival answers: "If I deploy $1M more, does capital survival
improve or degrade?"

Higher capital deployment typically degrades survival (less buffer),
but well-diversified deployment with high alpha can improve it.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class MarginalSurvivalResult:
    """Marginal survival analysis result."""
    strategy_id: str
    marginal_survival: float = 0.0  # Δsurvival_per_unit_capital
    pre_deployment_survival: float = 0.0
    post_deployment_survival: float = 0.0
    buffer_impact: float = 0.0  # change in buffer adequacy
    resilience_impact: float = 0.0  # change in drawdown resilience
    alpha_cushion_impact: float = 0.0  # alpha's contribution to survival
    improves_survival: bool = False
    threshold_safe: bool = True
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def summarize(self) -> str:
        delta = "improves" if self.improves_survival else "degrades"
        return (
            f"MarginalSurvival[{self.strategy_id}] {delta} survival: "
            f"{self.pre_deployment_survival:.3f}→{self.post_deployment_survival:.3f} "
            f"(Δ={self.marginal_survival:+.4f})"
        )


class MarginalSurvival:
    """Computes how additional capital deployment affects survival probability.

    Survival = f(buffer, diversification, alpha_cushion, tail_risk)
    dSurvival/dCapital = ∂Survival/∂buffer * dbuffer/dCapital
                         + ∂Survival/∂alpha * dalpha/dCapital
                         + ∂Survival/∂tail * dtail/dCapital
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self._config = config or {}
        self._buffer_sensitivity = self._config.get("buffer_sensitivity", 0.4)
        self._alpha_sensitivity = self._config.get("alpha_sensitivity", 0.3)
        self._diversification_sensitivity = self._config.get("diversification_sensitivity", 0.2)
        self._tail_sensitivity = self._config.get("tail_sensitivity", 0.1)

    def compute(self, strategy_id: str,
                total_capital: float,
                current_buffer: float,
                current_reserve: float,
                additional_capital: float,
                marginal_alpha: float = 0.0,
                marginal_risk: float = 0.0,
                current_survival: float = 0.75,
                diversification_benefit: float = 0.0) -> MarginalSurvivalResult:
        """Compute marginal survival impact of deploying additional capital."""
        if total_capital <= 0:
            return MarginalSurvivalResult(strategy_id=strategy_id)

        # Post-deployment buffer
        new_buffer = current_buffer
        new_reserve = current_reserve

        # Buffer impact: deploying capital reduces buffer ratio
        buffer_ratio_before = (current_buffer + current_reserve) / total_capital
        buffer_ratio_after = (new_buffer + new_reserve) / total_capital
        buffer_impact = -self._buffer_sensitivity * (buffer_ratio_before - buffer_ratio_after) * total_capital

        # Alpha cushion: additional alpha improves survival
        alpha_impact = self._alpha_sensitivity * marginal_alpha

        # Diversification benefit
        div_impact = self._diversification_sensitivity * diversification_benefit

        # Tail risk: more deployed = higher tail risk
        tail_impact = -self._tail_sensitivity * marginal_risk

        # Total marginal survival
        marginal = buffer_impact + alpha_impact + div_impact + tail_impact

        # Post-deployment survival
        post_survival = current_survival + marginal
        post_survival = max(0.0, min(1.0, post_survival))

        threshold = self._config.get("min_survival_threshold", 0.70)
        threshold_safe = post_survival >= threshold

        return MarginalSurvivalResult(
            strategy_id=strategy_id,
            marginal_survival=marginal,
            pre_deployment_survival=current_survival,
            post_deployment_survival=post_survival,
            buffer_impact=buffer_impact,
            resilience_impact=tail_impact,
            alpha_cushion_impact=alpha_impact,
            improves_survival=marginal > 0,
            threshold_safe=threshold_safe,
        )

    def compute_batch(self, strategies: List[Dict[str, Any]],
                      total_capital: float,
                      current_buffer: float,
                      current_reserve: float) -> List[MarginalSurvivalResult]:
        """Compute marginal survival for multiple strategies."""
        results = []
        for s in strategies:
            results.append(self.compute(
                strategy_id=s.get("strategy_id", ""),
                total_capital=total_capital,
                current_buffer=current_buffer,
                current_reserve=current_reserve,
                additional_capital=s.get("additional_capital", 0.0),
                marginal_alpha=s.get("marginal_alpha", 0.0),
                marginal_risk=s.get("marginal_risk", 0.0),
                current_survival=s.get("current_survival", 0.75),
                diversification_benefit=s.get("diversification_benefit", 0.0),
            ))
        return results

    def would_allocate(self, result: MarginalSurvivalResult) -> Tuple[bool, str]:
        """Determine if allocation should proceed based on survival impact."""
        if not result.threshold_safe:
            return False, (
                f"Post-allocation survival ({result.post_deployment_survival:.3f}) "
                f"below minimum threshold"
            )
        if result.improves_survival:
            return True, "Allocation improves capital survival"
        return True, "Allocation maintains survival above threshold"
