"""
Portfolio Scenario — What-If Portfolio Analysis

Simulates portfolio under different market scenarios:
    Market +10%, Market -10%, Vol +50%, Corr +30%, Liq -50%, Strategy Failure
"""

import uuid
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ScenarioResult:
    scenario_name: str
    portfolio_pnl: float = 0.0
    portfolio_risk: float = 0.0
    max_drawdown: float = 0.0
    capital_utilization: float = 0.0
    worst_asset: Optional[str] = None
    worst_impact: float = 0.0


class PortfolioScenario:
    """
    Simulates portfolio under various market scenarios.

    Scenarios:
    - Market +/-10%, +/-25%
    - Volatility +/-50%
    - Correlation +30%
    - Liquidity -50%
    - Strategy failure
    """

    def __init__(
        self,
        scenario_id: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.scenario_id = scenario_id or f"ps-{uuid.uuid4().hex[:12]}"
        self.config = config or {}

    def simulate(
        self,
        positions: Dict[str, float],
        scenarios: Optional[List[str]] = None,
    ) -> List[ScenarioResult]:
        """Run all specified scenarios."""
        results = []
        scenarios = scenarios or ["market_up_10", "market_down_10", "vol_up_50", "liq_down_50"]

        for scenario in scenarios:
            multiplier = self._get_scenario_multiplier(scenario)
            pnl = sum(pos * multiplier for pos in positions.values()) if positions else 0.0
            risk = abs(pnl) * 2.0
            drawdown = abs(pnl) * 1.5

            results.append(ScenarioResult(
                scenario_name=scenario,
                portfolio_pnl=pnl,
                portfolio_risk=risk,
                max_drawdown=drawdown,
                capital_utilization=min(1.0, 0.5 + abs(pnl) * 0.1),
            ))

        return results

    def _get_scenario_multiplier(self, scenario: str) -> float:
        return {
            "market_up_10": 0.10,
            "market_up_25": 0.25,
            "market_down_10": -0.10,
            "market_down_25": -0.25,
            "vol_up_50": -0.15,
            "vol_down_50": 0.05,
            "corr_up_30": -0.08,
            "liq_down_50": -0.20,
            "strategy_failure": -0.30,
        }.get(scenario, 0.0)
