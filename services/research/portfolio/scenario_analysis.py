"""Scenario Analysis — evaluate portfolio across market regimes.

Supports scenario types:
* Bull Market — rising prices, low volatility
* Bear Market — falling prices, high volatility
* Sideways — range-bound, moderate volatility
* High Inflation — rising inflation expectations
* Recession — economic contraction
* Custom — user-defined macro scenario
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ScenarioType(str, Enum):
    """Predefined scenario types."""

    BULL = "bull"
    BEAR = "bear"
    SIDEWAYS = "sideways"
    HIGH_INFLATION = "high_inflation"
    RECESSION = "recession"
    RECOVERY = "recovery"
    CUSTOM = "custom"


@dataclass
class ScenarioDefinition:
    """Definition of a market scenario."""

    name: str
    scenario_type: ScenarioType
    description: str
    expected_return: float = 0.0
    volatility: float = 0.15
    correlation_regime: str = "normal"  # normal, high, low
    factor_returns: Dict[str, float] = field(default_factory=dict)
    sector_returns: Dict[str, float] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "type": self.scenario_type.value,
            "description": self.description,
            "expected_return": self.expected_return,
            "volatility": self.volatility,
            "correlation_regime": self.correlation_regime,
        }


@dataclass
class ScenarioResult:
    """Result of portfolio analysis under a single scenario."""

    scenario: ScenarioDefinition
    portfolio_return: float = 0.0
    portfolio_risk: float = 0.0
    sharpe_ratio: float = 0.0
    var_95: float = 0.0
    cvar_95: float = 0.0
    asset_contributions: Dict[str, float] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scenario": self.scenario.name,
            "scenario_type": self.scenario.scenario_type.value,
            "portfolio_return": self.portfolio_return,
            "portfolio_risk": self.portfolio_risk,
            "sharpe_ratio": self.sharpe_ratio,
            "var_95": self.var_95,
            "cvar_95": self.cvar_95,
        }


@dataclass
class ScenarioReport:
    """Aggregated scenario analysis report."""

    portfolio_id: str = ""
    results: List[ScenarioResult] = field(default_factory=list)
    best_scenario: str = ""
    worst_scenario: str = ""
    best_return: float = 0.0
    worst_return: float = 0.0
    return_range: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "portfolio_id": self.portfolio_id,
            "num_scenarios": len(self.results),
            "best_scenario": self.best_scenario,
            "worst_scenario": self.worst_scenario,
            "best_return": self.best_return,
            "worst_return": self.worst_return,
            "return_range": self.return_range,
            "results": [r.to_dict() for r in self.results],
            "metadata": self.metadata,
        }


class ScenarioAnalyzer:
    """Analyze portfolio performance across multiple market scenarios.

    Evaluates how the portfolio would perform under different
    macro-economic and market regime scenarios.
    """

    # Predefined market regime scenarios
    DEFAULT_SCENARIOS: Dict[str, Dict[str, Any]] = {
        "bull_market": {
            "type": ScenarioType.BULL,
            "description": "Strong bull market with low volatility",
            "expected_return": 0.30,
            "volatility": 0.12,
            "correlation_regime": "low",
            "factor_returns": {
                "market": 0.30, "momentum": 0.25, "growth": 0.35,
            },
        },
        "bear_market": {
            "type": ScenarioType.BEAR,
            "description": "Severe bear market with high volatility",
            "expected_return": -0.25,
            "volatility": 0.35,
            "correlation_regime": "high",
            "factor_returns": {
                "market": -0.25, "value": -0.10, "quality": -0.05,
            },
        },
        "sideways_market": {
            "type": ScenarioType.SIDEWAYS,
            "description": "Range-bound market with moderate volatility",
            "expected_return": 0.02,
            "volatility": 0.15,
            "correlation_regime": "normal",
            "factor_returns": {
                "market": 0.02, "value": 0.05, "momentum": -0.05,
            },
        },
        "high_inflation": {
            "type": ScenarioType.HIGH_INFLATION,
            "description": "High inflation environment",
            "expected_return": -0.05,
            "volatility": 0.22,
            "correlation_regime": "high",
            "factor_returns": {
                "market": -0.05, "value": 0.10, "size": -0.10,
            },
            "sector_returns": {
                "energy": 0.15, "materials": 0.10, "tech": -0.15,
            },
        },
        "recession": {
            "type": ScenarioType.RECESSION,
            "description": "Economic recession",
            "expected_return": -0.20,
            "volatility": 0.30,
            "correlation_regime": "high",
            "factor_returns": {
                "market": -0.20, "quality": 0.05, "momentum": -0.15,
            },
        },
        "recovery": {
            "type": ScenarioType.RECOVERY,
            "description": "Post-recession recovery",
            "expected_return": 0.25,
            "volatility": 0.18,
            "correlation_regime": "low",
            "factor_returns": {
                "market": 0.25, "size": 0.20, "value": 0.15,
            },
        },
    }

    def __init__(self) -> None:
        self._custom_scenarios: Dict[str, ScenarioDefinition] = {}

    async def analyze(
        self,
        weights: Dict[str, float],
        universe: Optional[List[str]] = None,
        scenarios: Optional[List[str]] = None,
        cov_matrix: Optional[Dict[str, Dict[str, float]]] = None,
        asset_factor_exposures: Optional[Dict[str, Dict[str, float]]] = None,
        **kwargs: Any,
    ) -> ScenarioReport:
        """Analyze portfolio across multiple scenarios.

        Args:
            weights: Portfolio weights.
            universe: Asset universe.
            scenarios: Scenarios to analyze.
            cov_matrix: Covariance matrix.
            asset_factor_exposures: Factor exposures per asset.

        Returns:
            ScenarioReport with results per scenario.
        """
        report = ScenarioReport(
            portfolio_id=kwargs.get("portfolio_id", ""),
        )

        if scenarios is None:
            scenarios = list(self.DEFAULT_SCENARIOS.keys())

        for scenario_name in scenarios:
            definition = self.DEFAULT_SCENARIOS.get(scenario_name)
            if definition is None:
                definition = self._custom_scenarios.get(scenario_name)
            if definition is None:
                continue

            scenario = self._build_scenario(scenario_name, definition)
            result = self._evaluate_scenario(
                scenario, weights, cov_matrix,
                asset_factor_exposures,
            )
            report.results.append(result)

        if report.results:
            report.best_return = max(
                r.portfolio_return for r in report.results
            )
            report.worst_return = min(
                r.portfolio_return for r in report.results
            )
            report.best_scenario = max(
                report.results, key=lambda r: r.portfolio_return
            ).scenario.name
            report.worst_scenario = min(
                report.results, key=lambda r: r.portfolio_return
            ).scenario.name
            report.return_range = report.best_return - report.worst_return

        report.metadata["num_scenarios"] = len(report.results)
        return report

    def add_custom_scenario(
        self, scenario: ScenarioDefinition
    ) -> None:
        """Register a custom scenario."""
        self._custom_scenarios[scenario.name] = scenario

    def _build_scenario(
        self, name: str, definition: Dict[str, Any]
    ) -> ScenarioDefinition:
        return ScenarioDefinition(
            name=name,
            scenario_type=ScenarioType(definition.get("type", "custom")),
            description=definition.get("description", ""),
            expected_return=definition.get("expected_return", 0.0),
            volatility=definition.get("volatility", 0.15),
            correlation_regime=definition.get("correlation_regime", "normal"),
            factor_returns=definition.get("factor_returns", {}),
            sector_returns=definition.get("sector_returns", {}),
        )

    def _evaluate_scenario(
        self,
        scenario: ScenarioDefinition,
        weights: Dict[str, float],
        cov_matrix: Optional[Dict[str, Dict[str, float]]],
        asset_factor_exposures: Optional[Dict[str, Dict[str, float]]],
    ) -> ScenarioResult:
        """Evaluate portfolio performance under a scenario."""
        assets = list(weights.keys())

        # Portfolio return under scenario
        portfolio_return = 0.0
        asset_contributions: Dict[str, float] = {}

        for asset in assets:
            w = weights.get(asset, 0.0)
            # Asset return = scenario expected return + factor overlay
            asset_ret = scenario.expected_return

            # Add factor contributions if available
            if asset_factor_exposures and asset in asset_factor_exposures:
                for factor, exposure in asset_factor_exposures[asset].items():
                    factor_ret = scenario.factor_returns.get(factor, 0.0)
                    asset_ret += exposure * factor_ret

            asset_contributions[asset] = w * asset_ret
            portfolio_return += w * asset_ret

        # Portfolio risk under scenario
        if cov_matrix:
            variance = 0.0
            for i in assets:
                for j in assets:
                    variance += (
                        weights.get(i, 0.0)
                        * weights.get(j, 0.0)
                        * cov_matrix.get(i, {}).get(j, 0.0)
                    )
            portfolio_risk = max(variance, 0.0) ** 0.5
        else:
            portfolio_risk = scenario.volatility

        # Adjust for correlation regime
        if scenario.correlation_regime == "high":
            portfolio_risk *= 1.5
        elif scenario.correlation_regime == "low":
            portfolio_risk *= 0.7

        # Sharpe
        sharpe = portfolio_return / portfolio_risk if portfolio_risk > 0 else 0.0

        # VaR/CVaR estimates
        z_95 = 1.6449
        var_95 = z_95 * portfolio_risk
        cvar_95 = portfolio_risk * 0.1031 / 0.05  # normal ES at 95%

        return ScenarioResult(
            scenario=scenario,
            portfolio_return=portfolio_return,
            portfolio_risk=portfolio_risk,
            sharpe_ratio=sharpe,
            var_95=var_95,
            cvar_95=cvar_95,
            asset_contributions=asset_contributions,
        )
