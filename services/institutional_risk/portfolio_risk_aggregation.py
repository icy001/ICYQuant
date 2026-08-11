"""PortfolioRiskAggregation — aggregate risk across strategies within a portfolio."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from services.institutional_risk.risk_aggregation import (
    AggregatedRisk,
    AggregationLevel,
    RiskAggregationEngine,
)
from services.institutional_risk.strategy_risk_aggregation import StrategyRiskProfile


@dataclass
class PortfolioRiskProfile:
    """Risk profile for a multi-strategy portfolio."""

    portfolio_id: str
    var_95: float = 0.0
    var_99: float = 0.0
    expected_shortfall_95: float = 0.0
    expected_shortfall_99: float = 0.0
    drawdown_pct: float = 0.0
    max_drawdown_pct: float = 0.0
    volatility: float = 0.0
    sharpe: float = 0.0
    sortino: float = 0.0
    strategy_contributions: Dict[str, float] = field(default_factory=dict)
    correlation_risk: float = 0.0
    diversification_ratio: float = 1.0
    concentration_hhi: float = 0.0
    factor_exposures: Dict[str, float] = field(default_factory=dict)
    tail_dependence: float = 0.0
    liquidity_risk: float = 0.0
    strategy_count: int = 0


class PortfolioRiskAggregator:
    """Aggregates strategy-level risks into a portfolio-level risk profile.

    Accounts for inter-strategy correlations, factor exposures,
    and tail dependence.
    """

    def __init__(self):
        self._engine = RiskAggregationEngine()

    def aggregate(
        self,
        portfolio_id: str,
        strategies: Dict[str, StrategyRiskProfile],
        correlations: Optional[Dict[Tuple[str, str], float]] = None,
        factor_exposures: Optional[Dict[str, Dict[str, float]]] = None,
    ) -> PortfolioRiskProfile:
        """Aggregate strategies into a portfolio risk profile.

        Args:
            portfolio_id: portfolio identifier
            strategies: {strategy_id: StrategyRiskProfile} mapping
            correlations: pairwise strategy correlations
            factor_exposures: per-strategy factor exposures
        """
        if not strategies:
            return PortfolioRiskProfile(portfolio_id=portfolio_id)

        n = len(strategies)

        # extract risk components
        risk_components = {
            sid: s.var_99 for sid, s in strategies.items()
        }

        result = self._engine.aggregate(risk_components, correlations, AggregationLevel.PORTFOLIO)

        # compute diversification ratio
        sum_risk = sum(s.var_99 for s in strategies.values())
        diversification = result.total_risk / max(sum_risk, 1e-9)

        # aggregate factor exposures
        aggregate_factors: Dict[str, float] = {}
        if factor_exposures:
            for sid, factors in factor_exposures.items():
                weight = 1.0 / n
                for f_name, f_val in factors.items():
                    aggregate_factors[f_name] = aggregate_factors.get(f_name, 0.0) + f_val * weight

        # concentration HHI
        hhi = sum((1.0 / n) ** 2 for _ in strategies)

        # correlation risk
        corr_risk = 1.0 - diversification

        return PortfolioRiskProfile(
            portfolio_id=portfolio_id,
            var_95=result.var_95,
            var_99=result.var_99,
            expected_shortfall_95=result.expected_shortfall_95,
            expected_shortfall_99=result.expected_shortfall_99,
            strategy_contributions=result.marginal_risks,
            correlation_risk=corr_risk,
            diversification_ratio=diversification,
            concentration_hhi=hhi,
            factor_exposures=aggregate_factors,
            strategy_count=n,
        )

    def compute_incremental_portfolio_risk(
        self,
        current_profile: PortfolioRiskProfile,
        new_strategy: StrategyRiskProfile,
        correlation: float,
    ) -> float:
        """Compute incremental portfolio risk from adding a new strategy."""
        incremental = self._engine.compute_incremental_risk(
            current_profile.var_99,
            new_strategy.var_99,
            correlation,
        )
        return incremental - current_profile.var_99
