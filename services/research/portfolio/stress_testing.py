"""Stress Testing Engine — evaluate portfolio performance under extreme scenarios.

Supports stress scenarios:
* Historical Crash — replay historical crisis events
* Interest Rate Shock — sudden rate changes
* Volatility Spike — volatility regime change
* Liquidity Crisis — market freeze scenario
* Custom Scenario — user-defined shocks
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class StressScenario:
    """Definition of a stress scenario."""

    name: str
    description: str
    asset_shocks: Dict[str, float] = field(default_factory=dict)
    factor_shocks: Dict[str, float] = field(default_factory=dict)
    volatility_multiplier: float = 1.0
    correlation_break: bool = False
    liquidity_discount: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "num_asset_shocks": len(self.asset_shocks),
            "num_factor_shocks": len(self.factor_shocks),
            "volatility_multiplier": self.volatility_multiplier,
            "correlation_break": self.correlation_break,
            "liquidity_discount": self.liquidity_discount,
        }


@dataclass
class StressTestResult:
    """Result of a single stress scenario."""

    scenario: StressScenario
    portfolio_loss: float = 0.0
    portfolio_loss_pct: float = 0.0
    asset_losses: Dict[str, float] = field(default_factory=dict)
    factor_impacts: Dict[str, float] = field(default_factory=dict)
    liquidity_impact: float = 0.0
    recovery_time_estimate: int = 0  # days
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scenario": self.scenario.name,
            "portfolio_loss": self.portfolio_loss,
            "portfolio_loss_pct": self.portfolio_loss_pct,
            "liquidity_impact": self.liquidity_impact,
            "recovery_time_estimate": self.recovery_time_estimate,
            "worst_asset": max(
                self.asset_losses.items(), key=lambda x: x[1]
            )[0] if self.asset_losses else None,
        }


@dataclass
class StressTestReport:
    """Aggregated stress test report."""

    portfolio_id: str = ""
    results: List[StressTestResult] = field(default_factory=list)
    max_loss: float = 0.0
    max_loss_scenario: str = ""
    average_loss: float = 0.0
    var_stress_ratio: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "portfolio_id": self.portfolio_id,
            "num_scenarios": len(self.results),
            "max_loss": self.max_loss,
            "max_loss_scenario": self.max_loss_scenario,
            "average_loss": self.average_loss,
            "var_stress_ratio": self.var_stress_ratio,
            "results": [r.to_dict() for r in self.results],
            "metadata": self.metadata,
        }


class StressTestEngine:
    """Evaluate portfolio under extreme market scenarios.

    Applies predefined and custom stress scenarios to assess
    portfolio vulnerability to tail events.
    """

    # Predefined historical crisis scenarios
    DEFAULT_SCENARIOS: Dict[str, Dict[str, Any]] = {
        "2008_financial_crisis": {
            "description": "Global financial crisis (Sep-Oct 2008)",
            "equity_shock": -0.40,
            "credit_shock": -0.15,
            "vol_multiplier": 3.0,
            "correlation_break": True,
        },
        "2020_covid_crash": {
            "description": "COVID-19 pandemic crash (Feb-Mar 2020)",
            "equity_shock": -0.34,
            "vol_multiplier": 4.0,
            "correlation_break": True,
            "liquidity_discount": 0.85,
        },
        "interest_rate_shock": {
            "description": "Sudden 200bp rate hike",
            "equity_shock": -0.15,
            "bond_shock": -0.10,
            "vol_multiplier": 2.0,
        },
        "volatility_spike": {
            "description": "VIX spike to 50+",
            "equity_shock": -0.20,
            "vol_multiplier": 5.0,
            "correlation_break": True,
        },
        "liquidity_crisis": {
            "description": "Market-wide liquidity freeze",
            "equity_shock": -0.25,
            "liquidity_discount": 0.50,
            "vol_multiplier": 3.0,
        },
        "china_property_crisis": {
            "description": "China property sector stress",
            "equity_shock": -0.30,
            "sector_shocks": {"real_estate": -0.50, "financials": -0.30},
            "vol_multiplier": 2.5,
        },
    }

    def __init__(self) -> None:
        self._custom_scenarios: Dict[str, StressScenario] = {}

    async def run(
        self,
        weights: Dict[str, float],
        scenarios: Optional[List[str]] = None,
        portfolio_value: float = 1.0,
        asset_betas: Optional[Dict[str, float]] = None,
        **kwargs: Any,
    ) -> StressTestReport:
        """Run stress tests on portfolio.

        Args:
            weights: Portfolio weights.
            scenarios: List of scenario names to run (default: all).
            portfolio_value: Total portfolio value.
            asset_betas: Asset betas to market.

        Returns:
            StressTestReport with results for each scenario.
        """
        report = StressTestReport(portfolio_id=kwargs.get("portfolio_id", ""))

        # Determine which scenarios to run
        if scenarios is None:
            scenarios = list(self.DEFAULT_SCENARIOS.keys())
            scenarios.extend(self._custom_scenarios.keys())

        for scenario_name in scenarios:
            # Get scenario definition
            scenario_def = self.DEFAULT_SCENARIOS.get(scenario_name)
            if scenario_def is None:
                scenario_def = self._custom_scenarios.get(scenario_name)
            if scenario_def is None:
                continue

            scenario = self._build_scenario(scenario_name, scenario_def)
            result = self._apply_scenario(
                scenario, weights, portfolio_value, asset_betas
            )
            report.results.append(result)

        # Aggregate
        if report.results:
            report.max_loss = max(
                r.portfolio_loss_pct for r in report.results
            )
            report.max_loss_scenario = max(
                report.results,
                key=lambda r: r.portfolio_loss_pct,
            ).scenario.name
            report.average_loss = sum(
                r.portfolio_loss_pct for r in report.results
            ) / len(report.results)

        report.metadata["num_scenarios"] = len(report.results)
        return report

    def add_custom_scenario(
        self, scenario: StressScenario
    ) -> None:
        """Register a custom stress scenario."""
        self._custom_scenarios[scenario.name] = scenario

    def _build_scenario(
        self, name: str, definition: Dict[str, Any]
    ) -> StressScenario:
        """Build StressScenario from definition dict."""
        asset_shocks: Dict[str, float] = {}

        # Apply equity shock to all assets as baseline
        equity_shock = definition.get("equity_shock", 0.0)
        if equity_shock:
            asset_shocks["_all_equity"] = equity_shock

        # Sector-specific shocks
        sector_shocks = definition.get("sector_shocks", {})
        for sector, shock in sector_shocks.items():
            asset_shocks[f"sector_{sector}"] = shock

        # Factor shocks
        factor_shocks: Dict[str, float] = {}
        if definition.get("credit_shock"):
            factor_shocks["credit"] = definition["credit_shock"]
        if definition.get("bond_shock"):
            factor_shocks["rates"] = definition["bond_shock"]

        return StressScenario(
            name=name,
            description=definition.get("description", ""),
            asset_shocks=asset_shocks,
            factor_shocks=factor_shocks,
            volatility_multiplier=definition.get("vol_multiplier", 1.0),
            correlation_break=definition.get("correlation_break", False),
            liquidity_discount=definition.get("liquidity_discount", 1.0),
        )

    def _apply_scenario(
        self,
        scenario: StressScenario,
        weights: Dict[str, float],
        portfolio_value: float,
        asset_betas: Optional[Dict[str, float]],
    ) -> StressTestResult:
        """Apply a stress scenario and compute portfolio loss."""
        asset_losses: Dict[str, float] = {}

        base_equity_shock = scenario.asset_shocks.get("_all_equity", 0.0)

        for asset, weight in weights.items():
            # Base shock from equity
            loss = base_equity_shock

            # Adjust by asset beta if available
            if asset_betas and asset in asset_betas:
                loss *= asset_betas[asset]

            # Add sector-specific overlay
            for shock_key, shock_val in scenario.asset_shocks.items():
                if shock_key.startswith("sector_"):
                    # In production, look up sector from asset metadata
                    loss = min(loss, shock_val)  # worst of general/sector

            # Apply volatility multiplier
            loss *= scenario.volatility_multiplier

            asset_losses[asset] = loss

        # Portfolio-level loss
        portfolio_loss = 0.0
        for asset, weight in weights.items():
            asset_loss = asset_losses.get(asset, 0.0)
            portfolio_loss += weight * asset_loss

        # Liquidity impact
        liquidity_impact = (
            portfolio_value * portfolio_loss * (1.0 - scenario.liquidity_discount)
        )

        # Recovery estimate (rough heuristic)
        recovery_time = int(
            abs(portfolio_loss) * 252 * 2  # ~2x annualized recovery
        )

        return StressTestResult(
            scenario=scenario,
            portfolio_loss=abs(portfolio_loss) * portfolio_value,
            portfolio_loss_pct=abs(portfolio_loss),
            asset_losses=asset_losses,
            liquidity_impact=abs(liquidity_impact),
            recovery_time_estimate=recovery_time,
        )
