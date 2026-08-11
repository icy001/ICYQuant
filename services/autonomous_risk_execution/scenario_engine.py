"""
Scenario Engine — systematic what-if analysis for portfolio risk.

Generates and runs scenarios:
    - Volatility shocks (±20%, ±50%, ±100%)
    - Market moves (±5%, ±10%, ±20%)
    - Sector rotations
    - Correlation regime changes
    - Liquidity contractions
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


@dataclass
class Scenario:
    """A single scenario definition."""
    name: str
    description: str = ""
    shocks: dict[str, float] = field(default_factory=dict)  # {parameter: multiplier}
    correlation_shift: float = 0.0
    volatility_multiplier: float = 1.0
    liquidity_multiplier: float = 1.0


@dataclass
class ScenarioResult:
    """Result of running a single scenario."""
    scenario: Scenario
    portfolio_pnl_pct: float = 0.0
    portfolio_var: float = 0.0
    worst_asset_pnl: float = 0.0
    positions_after: dict[str, float] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


@dataclass
class ScenarioAnalysisResult:
    """Complete scenario analysis result."""
    id: str = field(default_factory=lambda: str(uuid4()))
    scenarios: list[ScenarioResult] = field(default_factory=list)
    worst_case_pnl: float = 0.0
    worst_case_scenario: str = ""
    avg_scenario_pnl: float = 0.0
    var_increase_max: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)


class ScenarioEngine:
    """
    Scenario analysis engine.

    Standard scenarios:
        1. Volatility +50%
        2. Volatility +100%
        3. Market -10%
        4. Market -20%
        5. Correlation +30% (diversification breakdown)
        6. Liquidity -40%
        7. Spread +100%
        8. Sector rotation shock
    """

    STANDARD_SCENARIOS: list[Scenario] = [
        Scenario("VOL_UP_50", "Volatility increases by 50%",
                 volatility_multiplier=1.50),
        Scenario("VOL_UP_100", "Volatility doubles",
                 volatility_multiplier=2.00),
        Scenario("MARKET_DOWN_10", "Broad market decline 10%",
                 shocks={"MARKET": -0.10}),
        Scenario("MARKET_DOWN_20", "Severe market decline 20%",
                 shocks={"MARKET": -0.20}),
        Scenario("CORR_SPIKE_30", "Correlation spike +30% (diversification failure)",
                 correlation_shift=0.30),
        Scenario("LIQUIDITY_DOWN_40", "Liquidity contracts 40%",
                 liquidity_multiplier=0.60),
        Scenario("SPREAD_UP_100", "Bid-ask spreads double",
                 shocks={"SPREAD": 2.0}),
        Scenario("SECTOR_ROTATION", "Major sector rotation",
                 shocks={"SECTOR_SHIFT": 0.15}),
        Scenario("TAIL_EVENT", "Tail event: vol +100%, market -15%, corr +50%",
                 volatility_multiplier=2.00, correlation_shift=0.50,
                 shocks={"MARKET": -0.15}),
    ]

    def __init__(self, custom_scenarios: Optional[list[Scenario]] = None) -> None:
        self._scenarios = self.STANDARD_SCENARIOS + (custom_scenarios or [])
        self._last_result: Optional[ScenarioAnalysisResult] = None

    async def run_all(
        self,
        positions: dict[str, float],
        base_vol: float = 0.15,
        assets_vol: Optional[dict[str, float]] = None,
    ) -> ScenarioAnalysisResult:
        """Run all scenarios on the current portfolio."""
        result = ScenarioAnalysisResult()
        vol_map = assets_vol or {}

        for scenario in self._scenarios:
            sr = ScenarioResult(scenario=scenario)

            # Estimate P&L impact
            market_shock = scenario.shocks.get("MARKET", 0)
            vol_mult = scenario.volatility_multiplier
            corr_shift = scenario.correlation_shift
            liq_mult = scenario.liquidity_multiplier

            # Simplified P&L estimation
            pnl = 0.0
            worst_asset_pnl = 0.0
            for asset, weight in positions.items():
                asset_vol = vol_map.get(asset, base_vol)
                # P&L impact: weight * shock * vol_mult * (1 + corr_shift)
                asset_pnl = abs(weight) * (
                    market_shock + (vol_mult - 1.0) * asset_vol
                    + corr_shift * asset_vol
                )
                pnl += asset_pnl
                worst_asset_pnl = max(worst_asset_pnl, asset_pnl)

            sr.portfolio_pnl_pct = pnl
            sr.portfolio_var = base_vol * vol_mult
            sr.worst_asset_pnl = worst_asset_pnl

            if pnl > 0.05:
                sr.warnings.append(f"Scenario {scenario.name}: P&L {pnl:.2%} exceeds 5%")

            result.scenarios.append(sr)

            if pnl > result.worst_case_pnl:
                result.worst_case_pnl = pnl
                result.worst_case_scenario = scenario.name

        if result.scenarios:
            result.avg_scenario_pnl = sum(
                s.portfolio_pnl_pct for s in result.scenarios
            ) / len(result.scenarios)

        result.timestamp = datetime.now()
        self._last_result = result

        logger.info(
            "Scenario analysis: %d scenarios, worst=%.2f%% (%s)",
            len(result.scenarios), result.worst_case_pnl * 100,
            result.worst_case_scenario,
        )
        return result

    def add_scenario(self, scenario: Scenario) -> None:
        """Add a custom scenario."""
        self._scenarios.append(scenario)

    @property
    def last_result(self) -> Optional[ScenarioAnalysisResult]:
        return self._last_result
