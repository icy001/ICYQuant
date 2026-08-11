"""MarginalRisk — incremental risk analysis per unit of capital.

Computes how much additional risk each unit of capital brings
to the portfolio and the overall capital pool.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class MarginalRiskResult:
    """Result of marginal risk computation."""

    strategy_id: str
    incremental_portfolio_risk: float = 0.0
    incremental_capital: float = 0.0
    marginal_risk_pct: float = 0.0
    var_contribution: float = 0.0
    es_contribution: float = 0.0
    risk_budget_impact: float = 0.0
    correlation_impact: float = 0.0
    acceptable: bool = True
    reason: str = ""


@dataclass
class MarginalRiskConfig:
    """Configuration for marginal risk analysis."""

    max_marginal_risk_pct: float = 0.15  # 15% max marginal risk
    min_risk_budget_impact: float = -0.5  # no more than 50% budget consumption
    correlation_warning_threshold: float = 0.70


class MarginalRiskAnalyzer:
    """Analyzes marginal risk for capital allocation decisions.

    Usage::

        analyzer = MarginalRiskAnalyzer()
        result = analyzer.analyze(
            strategy_id="strat_A",
            incremental_capital=10_000_000,
            current_portfolio_var=8_000_000,
            strategy_var=2_000_000,
            correlation=0.3,
        )
        if not result.acceptable:
            print(f"Reject: {result.reason}")
    """

    def __init__(self, config: Optional[MarginalRiskConfig] = None):
        self.config = config or MarginalRiskConfig()

    def analyze(
        self,
        strategy_id: str,
        incremental_capital: float,
        current_portfolio_var: float,
        strategy_var: float,
        correlation: float = 0.3,
        risk_budget_total: float = 0.0,
        risk_budget_used: float = 0.0,
    ) -> MarginalRiskResult:
        """Compute marginal risk of adding capital to a strategy.

        Args:
            strategy_id: strategy identifier
            incremental_capital: amount of capital being added
            current_portfolio_var: current portfolio VaR (99%)
            strategy_var: current strategy VaR (99%)
            correlation: correlation to existing portfolio
            risk_budget_total: total risk budget
            risk_budget_used: currently used risk budget
        """
        # incremental portfolio risk
        incremental_var = (
            current_portfolio_var ** 2
            + strategy_var ** 2
            + 2 * correlation * current_portfolio_var * strategy_var
        ) ** 0.5
        incremental_portfolio_risk = incremental_var - current_portfolio_var

        # marginal risk %
        marginal_risk_pct = 0.0
        if incremental_capital > 0:
            marginal_risk_pct = incremental_portfolio_risk / incremental_capital

        # risk budget impact
        risk_budget_impact = 0.0
        if risk_budget_total > 0:
            risk_budget_impact = incremental_portfolio_risk / risk_budget_total

        # acceptability checks
        acceptable = True
        reasons: List[str] = []

        if marginal_risk_pct > self.config.max_marginal_risk_pct:
            acceptable = False
            reasons.append(
                f"Marginal risk {marginal_risk_pct:.1%} exceeds max {self.config.max_marginal_risk_pct:.1%}"
            )

        if risk_budget_impact > abs(self.config.min_risk_budget_impact):
            acceptable = False
            reasons.append(
                f"Risk budget impact {risk_budget_impact:.1%} exceeds threshold"
            )

        if correlation > self.config.correlation_warning_threshold:
            acceptable = False
            reasons.append(
                f"Correlation {correlation:.2f} exceeds warning threshold {self.config.correlation_warning_threshold:.2f}"
            )

        return MarginalRiskResult(
            strategy_id=strategy_id,
            incremental_portfolio_risk=incremental_portfolio_risk,
            incremental_capital=incremental_capital,
            marginal_risk_pct=marginal_risk_pct,
            var_contribution=incremental_portfolio_risk,
            es_contribution=incremental_portfolio_risk * 1.3,
            risk_budget_impact=risk_budget_impact,
            correlation_impact=correlation,
            acceptable=acceptable,
            reason="; ".join(reasons) if reasons else "OK",
        )

    def compute_mce(
        self,
        marginal_alpha: float,
        marginal_risk_pct: float,
        marginal_cost_pct: float = 0.0,
    ) -> float:
        """Compute Marginal Capital Efficiency (MCE).

        MCE = Marginal Alpha / Marginal Cost
        Risk-Adjusted MCE = Marginal Alpha / (Marginal Risk + Marginal Cost)
        """
        denominator = marginal_risk_pct + marginal_cost_pct
        if denominator <= 0:
            return 0.0
        return marginal_alpha / denominator
