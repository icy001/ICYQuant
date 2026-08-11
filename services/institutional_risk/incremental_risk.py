"""IncrementalRisk — risk added by a new position or strategy.

Computes the increase in portfolio/capital risk when adding
a new component, accounting for correlation structure.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class IncrementalRiskResult:
    """Result of incremental risk computation."""

    component_id: str
    current_portfolio_risk: float = 0.0
    new_component_risk: float = 0.0
    new_portfolio_risk: float = 0.0
    incremental_risk: float = 0.0
    incremental_risk_pct: float = 0.0
    var_increase: float = 0.0
    es_increase: float = 0.0
    correlation_used: float = 0.0
    diversification_loss: float = 0.0


class IncrementalRiskAnalyzer:
    """Computes incremental risk from adding new components.

    Usage::

        analyzer = IncrementalRiskAnalyzer()
        result = analyzer.compute(
            current_risk=8_000_000,
            new_risk=2_000_000,
            correlation=0.3,
        )
        print(f"Risk increases by {result.incremental_risk:.0f}")
    """

    def compute(
        self,
        component_id: str,
        current_portfolio_risk: float,
        new_component_risk: float,
        correlation: float = 0.3,
        capital_base: float = 0.0,
    ) -> IncrementalRiskResult:
        """Compute incremental risk from adding a component.

        Uses the variance-covariance formula:
            σ_new² = σ_old² + σ_new² + 2ρ σ_old σ_new

        Args:
            component_id: identifier for the new component
            current_portfolio_risk: current portfolio risk (VaR or vol)
            new_component_risk: risk of the new component
            correlation: correlation to existing portfolio
            capital_base: base capital for percentage calculation
        """
        new_portfolio_var = (
            current_portfolio_risk ** 2
            + new_component_risk ** 2
            + 2 * correlation * current_portfolio_risk * new_component_risk
        )

        if new_portfolio_var <= 0:
            return IncrementalRiskResult(
                component_id=component_id,
                correlation_used=correlation,
            )

        new_portfolio_risk = new_portfolio_var ** 0.5
        incremental_risk = new_portfolio_risk - current_portfolio_risk

        incremental_risk_pct = 0.0
        if capital_base > 0:
            incremental_risk_pct = incremental_risk / capital_base

        # diversification loss: how much correlation reduces benefit
        independent_risk = (current_portfolio_risk ** 2 + new_component_risk ** 2) ** 0.5
        diversification_loss = new_portfolio_risk / max(independent_risk, 1e-9)

        return IncrementalRiskResult(
            component_id=component_id,
            current_portfolio_risk=current_portfolio_risk,
            new_component_risk=new_component_risk,
            new_portfolio_risk=new_portfolio_risk,
            incremental_risk=incremental_risk,
            incremental_risk_pct=incremental_risk_pct,
            var_increase=incremental_risk,
            es_increase=incremental_risk * 1.3,
            correlation_used=correlation,
            diversification_loss=diversification_loss,
        )

    def compute_batch(
        self,
        current_portfolio_risk: float,
        candidates: List[Dict[str, Any]],
    ) -> List[IncrementalRiskResult]:
        """Compute incremental risk for multiple candidates.

        Args:
            current_portfolio_risk: current portfolio risk
            candidates: list of {"id": "...", "risk": float, "correlation": float}
        """
        results = []
        for c in candidates:
            result = self.compute(
                component_id=c["id"],
                current_portfolio_risk=current_portfolio_risk,
                new_component_risk=c["risk"],
                correlation=c.get("correlation", 0.3),
            )
            results.append(result)
        return results

    def rank_by_efficiency(
        self,
        results: List[IncrementalRiskResult],
        expected_returns: Optional[Dict[str, float]] = None,
    ) -> List[IncrementalRiskResult]:
        """Rank candidates by risk-adjusted return efficiency.

        Lower incremental risk per unit of return is better.
        """
        if not expected_returns:
            return sorted(results, key=lambda r: r.incremental_risk)

        def efficiency(r: IncrementalRiskResult) -> float:
            ret = expected_returns.get(r.component_id, 0.0)
            if r.incremental_risk <= 0:
                return -1e9
            return ret / r.incremental_risk

        return sorted(results, key=efficiency, reverse=True)
