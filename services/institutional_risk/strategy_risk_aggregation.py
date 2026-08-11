"""StrategyRiskAggregation — aggregate risk within a single strategy."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from services.institutional_risk.risk_aggregation import (
    AggregatedRisk,
    AggregationLevel,
    RiskAggregationEngine,
    RiskComponent,
)


@dataclass
class StrategyRiskProfile:
    """Complete risk profile for a single strategy."""

    strategy_id: str
    var_95: float = 0.0
    var_99: float = 0.0
    expected_shortfall_95: float = 0.0
    expected_shortfall_99: float = 0.0
    drawdown_pct: float = 0.0
    max_drawdown_pct: float = 0.0
    volatility: float = 0.0
    leverage: float = 1.0
    factor_exposures: Dict[str, float] = field(default_factory=dict)
    position_risks: Dict[str, float] = field(default_factory=dict)
    tail_risk: float = 0.0
    liquidity_risk: float = 0.0
    concentration: float = 0.0
    sharpe: float = 0.0
    sortino: float = 0.0


class StrategyRiskAggregator:
    """Aggregates risk at the individual strategy level.

    Combines position-level risks within a strategy to produce
    a strategy-level risk profile.
    """

    def __init__(self):
        self._engine = RiskAggregationEngine()

    def aggregate(
        self,
        strategy_id: str,
        position_risks: Dict[str, float],
        correlations: Optional[Dict[str, float]] = None,
        leverage: float = 1.0,
    ) -> StrategyRiskProfile:
        """Aggregate position risks into a strategy risk profile.

        Args:
            strategy_id: identifier for the strategy
            position_risks: {position_id: risk_value} mapping
            correlations: optional pairwise correlations
            leverage: strategy leverage multiplier
        """
        if not position_risks:
            return StrategyRiskProfile(strategy_id=strategy_id)

        # convert to dict format expected by the engine
        components = position_risks
        corr_dict = {}
        if correlations:
            keys = list(correlations.keys())
            for i in range(len(keys)):
                for j in range(i + 1, len(keys)):
                    # approximate from list
                    pass

        result = self._engine.aggregate(components, corr_dict, AggregationLevel.STRATEGY)

        # apply leverage scaling
        vol = sum(components.values()) * leverage / max(len(components), 1)

        return StrategyRiskProfile(
            strategy_id=strategy_id,
            var_95=result.var_95 * leverage,
            var_99=result.var_99 * leverage,
            expected_shortfall_95=result.expected_shortfall_95 * leverage,
            expected_shortfall_99=result.expected_shortfall_99 * leverage,
            volatility=vol,
            leverage=leverage,
            position_risks=components,
            concentration=result.concentration_index,
        )

    def compute_marginal_risk(
        self,
        profile: StrategyRiskProfile,
        new_position_risk: float,
        correlation_to_existing: float = 0.3,
    ) -> float:
        """Compute marginal risk of adding a new position to the strategy."""
        current = profile.var_99
        incremental = self._engine.compute_incremental_risk(
            current, new_position_risk, correlation_to_existing
        )
        return incremental - current
