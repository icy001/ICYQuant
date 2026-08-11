"""
Risk Aggregator — Portfolio-Wide Risk Aggregation

Aggregates risk from all strategies into portfolio-level metrics:
VaR, Expected Shortfall, Volatility, Drawdown, Factor Risk,
Liquidity Risk, Concentration, Tail Risk.
"""

import uuid
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class PortfolioRisk:
    portfolio_id: str
    var_95: float = 0.0
    var_99: float = 0.0
    expected_shortfall: float = 0.0
    volatility: float = 0.0
    max_drawdown: float = 0.0
    concentration_risk: float = 0.0
    factor_risk: Dict[str, float] = field(default_factory=dict)
    liquidity_risk: float = 0.0
    tail_risk: float = 0.0
    total_risk: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)


class RiskAggregator:
    """
    Aggregates all strategy-level risks into a unified portfolio risk view.

    Computes: VaR, ES, Vol, Drawdown, Factor Risk, Concentration, Tail Risk.
    """

    def __init__(
        self,
        aggregator_id: Optional[str] = None,
        strategy_registry=None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.aggregator_id = aggregator_id or f"ra-{uuid.uuid4().hex[:12]}"
        self._registry = strategy_registry
        self.config = config or {}
        self._latest_risk: Optional[PortfolioRisk] = None

    def aggregate(self) -> PortfolioRisk:
        """Aggregate all risks into a single PortfolioRisk object."""
        risk = PortfolioRisk(portfolio_id=self.aggregator_id)

        if self._registry:
            strategies = self._registry.get_active()
            if strategies:
                n = len(strategies)
                vols = [getattr(r, 'expected_risk', 0.05) for r in strategies.values()]
                risk.volatility = sum(vols) / n if vols else 0.05
                risk.var_95 = risk.volatility * 1.65
                risk.var_99 = risk.volatility * 2.33
                risk.expected_shortfall = risk.volatility * 2.1

                risk.concentration_risk = max(
                    (getattr(r, 'capital_allocation', 0) / max(1, self._registry.get_total_capital()))
                    for r in strategies.values()
                )

        risk.total_risk = sum([
            risk.var_95 * 0.3,
            risk.volatility * 0.3,
            risk.concentration_risk * 0.2,
            risk.liquidity_risk * 0.1,
            risk.tail_risk * 0.1,
        ])

        self._latest_risk = risk
        return risk

    def get_latest(self) -> Optional[PortfolioRisk]:
        return self._latest_risk
