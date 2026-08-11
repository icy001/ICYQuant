"""Marginal Risk — computes marginal risk for incremental capital.

Marginal risk answers: "If I add $1M more, how much additional
portfolio risk does it create?"

Considers: standalone risk, correlation contribution, and
risk budget consumption.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class MarginalRiskResult:
    """Marginal risk analysis result."""
    strategy_id: str
    marginal_risk: float = 0.0  # marginal contribution to portfolio risk
    standalone_risk: float = 0.0
    correlation_contribution: float = 0.0
    risk_budget_consumed: float = 0.0
    risk_budget_limit: float = 0.0
    diversification_benefit: float = 0.0  # how much diversification helps
    risk_efficiency: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def summarize(self) -> str:
        return (
            f"MarginalRisk[{self.strategy_id}] marginal={self.marginal_risk:.4f} "
            f"standalone={self.standalone_risk:.4f} div_benefit={self.diversification_benefit:.2%}"
        )


class MarginalRisk:
    """Computes marginal risk contribution for capital allocation.

    Marginal Risk = ∂σ_portfolio / ∂w_i = (Σ w_j * σ_ij) / σ_portfolio
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self._config = config or {}
        self._risk_free_rate = self._config.get("risk_free_rate", 0.02)

    def compute(self, strategy_id: str,
                weight: float,
                volatility: float,
                portfolio_volatility: float,
                correlations: Optional[Dict[str, float]] = None,
                other_weights: Optional[Dict[str, float]] = None,
                other_volatilities: Optional[Dict[str, float]] = None,
                risk_budget: float = 0.0) -> MarginalRiskResult:
        """Compute marginal risk contribution.

        For simplicity: marginal_risk ≈ weight * vol^2 / portfolio_vol
        Plus correlation-weighted contributions from other strategies.
        """
        correlations = correlations or {}
        other_weights = other_weights or {}
        other_volatilities = other_volatilities or {}

        if portfolio_volatility <= 0:
            standalone = volatility * weight
            return MarginalRiskResult(
                strategy_id=strategy_id,
                marginal_risk=standalone,
                standalone_risk=standalone,
            )

        # Standalone contribution
        standalone_contrib = (weight * volatility ** 2) / portfolio_volatility

        # Correlation-weighted contribution
        corr_contrib = 0.0
        for other_id, other_w in other_weights.items():
            corr = correlations.get(other_id, 0.0)
            other_vol = other_volatilities.get(other_id, volatility)
            corr_contrib += other_w * volatility * other_vol * corr

        corr_contrib /= portfolio_volatility

        # Total marginal risk
        marginal_risk = standalone_contrib + corr_contrib

        # Diversification benefit: how much lower than standalone
        standalone_risk = weight * volatility
        div_benefit = 1.0 - (marginal_risk / standalone_risk) if standalone_risk > 0 else 0.0

        # Risk budget
        budget_consumed = marginal_risk
        risk_efficiency = 1.0 - (budget_consumed / risk_budget) if risk_budget > 0 else 0.5

        return MarginalRiskResult(
            strategy_id=strategy_id,
            marginal_risk=marginal_risk,
            standalone_risk=standalone_risk,
            correlation_contribution=corr_contrib,
            risk_budget_consumed=budget_consumed,
            risk_budget_limit=risk_budget,
            diversification_benefit=div_benefit,
            risk_efficiency=risk_efficiency,
        )

    def compute_from_covariance(self, strategy_id: str,
                                 weights: Dict[str, float],
                                 cov_matrix: Dict[str, Dict[str, float]],
                                 risk_budget: float = 0.0) -> MarginalRiskResult:
        """Compute marginal risk from full covariance matrix.

        Marginal risk = (Cov * w)_i / σ_portfolio
        """
        n = len(weights)

        # Portfolio variance
        portfolio_var = 0.0
        for i, wi in weights.items():
            for j, wj in weights.items():
                cov_ij = cov_matrix.get(i, {}).get(j, 0.0)
                portfolio_var += wi * wj * cov_ij

        portfolio_vol = portfolio_var ** 0.5

        if portfolio_vol <= 0:
            return MarginalRiskResult(
                strategy_id=strategy_id,
                marginal_risk=0.0,
            )

        # Marginal risk = (Cov * w)_i / σ
        cov_sum = 0.0
        for j, wj in weights.items():
            cov_ij = cov_matrix.get(strategy_id, {}).get(j, 0.0)
            cov_sum += wj * cov_ij

        marginal_risk = cov_sum / portfolio_vol
        weight = weights.get(strategy_id, 0.0)
        volatility = cov_matrix.get(strategy_id, {}).get(strategy_id, 0.0) ** 0.5
        standalone_risk = weight * volatility

        return MarginalRiskResult(
            strategy_id=strategy_id,
            marginal_risk=marginal_risk,
            standalone_risk=standalone_risk,
            risk_budget_consumed=marginal_risk,
            risk_budget_limit=risk_budget,
            diversification_benefit=1.0 - (marginal_risk / standalone_risk) if standalone_risk > 0 else 0.0,
        )

    def batch_compute(self, strategies: Dict[str, Dict[str, float]],
                      portfolio_volatility: float,
                      correlations: Dict[str, Dict[str, float]],
                      risk_budget: float = 0.0) -> List[MarginalRiskResult]:
        """Compute marginal risk for multiple strategies."""
        results = []
        for sid, params in strategies.items():
            result = self.compute(
                strategy_id=sid,
                weight=params.get("weight", 0.0),
                volatility=params.get("volatility", 0.0),
                portfolio_volatility=portfolio_volatility,
                correlations=correlations.get(sid, {}),
                risk_budget=risk_budget,
            )
            results.append(result)
        return results
