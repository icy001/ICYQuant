"""CapitalRiskAggregation — aggregate portfolio risks to capital pool level."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from services.institutional_risk.risk_aggregation import (
    AggregatedRisk,
    AggregationLevel,
    RiskAggregationEngine,
)
from services.institutional_risk.portfolio_risk_aggregation import PortfolioRiskProfile


@dataclass
class CapitalRiskProfile:
    """Risk profile for the entire capital pool."""

    var_95: float = 0.0
    var_99: float = 0.0
    expected_shortfall_95: float = 0.0
    expected_shortfall_99: float = 0.0
    drawdown_pct: float = 0.0
    max_drawdown_pct: float = 0.0
    total_capital: float = 0.0
    risk_capital_ratio: float = 0.0
    portfolio_contributions: Dict[str, float] = field(default_factory=dict)
    correlation_risk: float = 0.0
    diversification_ratio: float = 1.0
    tail_risk_score: float = 0.0
    survival_score: float = 100.0
    risk_budget_total: float = 0.0
    risk_budget_used: float = 0.0
    risk_budget_available: float = 0.0
    portfolio_count: int = 0
    strategy_count: int = 0
    mode: str = "NORMAL"


class CapitalRiskAggregator:
    """Aggregates portfolio-level risks to the capital pool level.

    This is the top level of risk aggregation, accounting for
    cross-portfolio correlations and capital constraints.
    """

    def __init__(self):
        self._engine = RiskAggregationEngine()

    def aggregate(
        self,
        capital_pool: float,
        portfolios: Dict[str, PortfolioRiskProfile],
        cross_portfolio_correlations: Optional[Dict[Tuple[str, str], float]] = None,
        risk_budget_ratio: float = 0.08,
    ) -> CapitalRiskProfile:
        """Aggregate portfolios to capital pool level.

        Args:
            capital_pool: total capital in the pool
            portfolios: {portfolio_id: PortfolioRiskProfile}
            cross_portfolio_correlations: pairwise correlations between portfolios
            risk_budget_ratio: risk budget as fraction of capital
        """
        if not portfolios:
            return CapitalRiskProfile(total_capital=capital_pool)

        n = len(portfolios)
        total_strategies = sum(p.strategy_count for p in portfolios.values())

        # extract risk components
        risk_components = {
            pid: p.var_99 for pid, p in portfolios.items()
        }

        result = self._engine.aggregate(
            risk_components,
            cross_portfolio_correlations,
            AggregationLevel.CAPITAL_POOL,
        )

        # risk budget
        risk_budget_total = capital_pool * risk_budget_ratio
        risk_budget_used = result.total_risk
        risk_budget_available = max(0.0, risk_budget_total - risk_budget_used)

        # drawdown aggregate (worst case)
        max_dd = max((p.drawdown_pct for p in portfolios.values()), default=0.0)

        # aggregate survival score
        avg_survival = (
            sum(
                # approximate per-portfolio survival
                max(0.0, 100.0 - p.var_99 * 2.0 - p.drawdown_pct)
                for p in portfolios.values()
            )
            / max(n, 1)
        )

        # correlation risk: 1 - diversification
        sum_risk = sum(p.var_99 for p in portfolios.values())
        diversification = result.total_risk / max(sum_risk, 1e-9)
        corr_risk = 1.0 - diversification

        return CapitalRiskProfile(
            var_95=result.var_95,
            var_99=result.var_99,
            expected_shortfall_95=result.expected_shortfall_95,
            expected_shortfall_99=result.expected_shortfall_99,
            drawdown_pct=max_dd,
            max_drawdown_pct=max_dd,
            total_capital=capital_pool,
            risk_capital_ratio=result.total_risk / max(capital_pool, 1e-9),
            portfolio_contributions=result.marginal_risks,
            correlation_risk=corr_risk,
            diversification_ratio=diversification,
            survival_score=avg_survival,
            risk_budget_total=risk_budget_total,
            risk_budget_used=risk_budget_used,
            risk_budget_available=risk_budget_available,
            portfolio_count=n,
            strategy_count=total_strategies,
        )

    def compute_capital_risk_ratio(self, profile: CapitalRiskProfile) -> float:
        """Risk-adjusted capital efficiency ratio."""
        if profile.var_99 <= 0:
            return 0.0
        return profile.total_capital / profile.var_99
