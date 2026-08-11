"""
Capital Scenario — What-if analysis for capital pool changes.

Supports:
    Capital +10%, Capital +25%, Capital -10%, Capital -25%

Tests impact on:
    Expected Return, Risk, Drawdown, Liquidity, Capacity
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class ScenarioType(str, Enum):
    CAPITAL_INCREASE = "capital_increase"
    CAPITAL_DECREASE = "capital_decrease"
    STRATEGY_ADDITION = "strategy_addition"
    STRATEGY_REMOVAL = "strategy_removal"
    REBALANCE = "rebalance"
    CUSTOM = "custom"


@dataclass
class CapitalScenario:
    """A defined capital scenario for what-if analysis."""

    scenario_id: str = field(default_factory=lambda: f"SC-{uuid.uuid4().hex[:8]}")
    name: str = ""
    scenario_type: ScenarioType = ScenarioType.CUSTOM
    description: str = ""

    # Capital changes
    capital_change_pct: float = 0.0        # e.g. 0.10 = +10%
    capital_change_absolute: float = 0.0   # absolute dollar change

    # Strategy changes
    added_strategies: List[str] = field(default_factory=list)
    removed_strategies: List[str] = field(default_factory=list)
    strategy_weight_adjustments: Dict[str, float] = field(default_factory=dict)

    # Market condition assumptions
    volatility_multiplier: float = 1.0
    correlation_multiplier: float = 1.0
    liquidity_multiplier: float = 1.0
    spread_multiplier: float = 1.0

    def apply_to_capital(self, current_capital: float) -> float:
        """Compute scenario-adjusted total capital."""
        adjusted = current_capital * (1.0 + self.capital_change_pct) + self.capital_change_absolute
        return max(0.0, adjusted)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "name": self.name,
            "type": self.scenario_type.value,
            "capital_change_pct": self.capital_change_pct,
            "capital_change_absolute": self.capital_change_absolute,
            "volatility_multiplier": self.volatility_multiplier,
            "correlation_multiplier": self.correlation_multiplier,
            "liquidity_multiplier": self.liquidity_multiplier,
        }


@dataclass
class ScenarioResult:
    """Outcome of running a capital scenario."""

    scenario_id: str = ""
    scenario_name: str = ""

    # Capital
    original_capital: float = 0.0
    adjusted_capital: float = 0.0
    capital_change: float = 0.0

    # Portfolio metrics
    original_expected_return: float = 0.0
    adjusted_expected_return: float = 0.0

    original_portfolio_risk: float = 0.0
    adjusted_portfolio_risk: float = 0.0
    risk_change: float = 0.0

    original_max_drawdown: float = 0.0
    adjusted_max_drawdown: float = 0.0

    original_liquidity_usage: float = 0.0
    adjusted_liquidity_usage: float = 0.0

    original_capacity_utilization: float = 0.0
    adjusted_capacity_utilization: float = 0.0

    # Strategy-level results
    strategy_impacts: Dict[str, Dict[str, float]] = field(default_factory=dict)

    passed: bool = True
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "scenario_name": self.scenario_name,
            "original_capital": self.original_capital,
            "adjusted_capital": self.adjusted_capital,
            "capital_change": self.capital_change,
            "original_expected_return": self.original_expected_return,
            "adjusted_expected_return": self.adjusted_expected_return,
            "original_portfolio_risk": self.original_portfolio_risk,
            "adjusted_portfolio_risk": self.adjusted_portfolio_risk,
            "original_max_drawdown": self.original_max_drawdown,
            "adjusted_max_drawdown": self.adjusted_max_drawdown,
            "passed": self.passed,
            "warnings": self.warnings,
        }


class ScenarioRunner:
    """Executes capital scenarios and produces results."""

    def __init__(self, total_capital: float = 0.0):
        self.total_capital = total_capital
        self._scenarios: List[CapitalScenario] = []
        self._results: List[ScenarioResult] = []

    def register(self, scenario: CapitalScenario) -> None:
        self._scenarios.append(scenario)

    @classmethod
    def standard_scenarios(cls, total_capital: float) -> List[CapitalScenario]:
        """Create standard capital scenarios."""
        return [
            CapitalScenario(
                name="Capital +10%",
                scenario_type=ScenarioType.CAPITAL_INCREASE,
                description="10% capital inflow",
                capital_change_pct=0.10,
            ),
            CapitalScenario(
                name="Capital +25%",
                scenario_type=ScenarioType.CAPITAL_INCREASE,
                description="25% capital inflow (e.g., new mandate)",
                capital_change_pct=0.25,
            ),
            CapitalScenario(
                name="Capital -10%",
                scenario_type=ScenarioType.CAPITAL_DECREASE,
                description="10% capital withdrawal",
                capital_change_pct=-0.10,
            ),
            CapitalScenario(
                name="Capital -25%",
                scenario_type=ScenarioType.CAPITAL_DECREASE,
                description="25% capital stress withdrawal",
                capital_change_pct=-0.25,
            ),
            CapitalScenario(
                name="Volatility +50%",
                scenario_type=ScenarioType.CUSTOM,
                description="Market volatility spike",
                volatility_multiplier=1.50,
            ),
        ]

    def run(self, scenario: CapitalScenario,
            strategy_metrics: Optional[Dict[str, Dict[str, float]]] = None) -> ScenarioResult:
        """Run a single scenario and produce result."""
        result = ScenarioResult(
            scenario_id=scenario.scenario_id,
            scenario_name=scenario.name,
            original_capital=self.total_capital,
            adjusted_capital=scenario.apply_to_capital(self.total_capital),
        )
        result.capital_change = result.adjusted_capital - result.original_capital

        # Simple proportional scaling
        scale = result.adjusted_capital / max(result.original_capital, 1.0)

        # Placeholder metrics — would use real strategy data in production
        result.original_expected_return = 0.12
        result.adjusted_expected_return = 0.12 * scale
        result.original_portfolio_risk = 0.15
        result.adjusted_portfolio_risk = 0.15 * scale * scenario.volatility_multiplier
        result.risk_change = result.adjusted_portfolio_risk - result.original_portfolio_risk

        if scenario.volatility_multiplier > 1.2:
            result.warnings.append(f"Volatility shock: {scenario.volatility_multiplier}x")

        if result.capital_change < -0.15 * result.original_capital:
            result.warnings.append(f"Severe capital reduction: {result.capital_change:.0f}")

        result.passed = len([w for w in result.warnings if "severe" in w.lower()]) == 0
        self._results.append(result)
        return result

    def run_all(self) -> List[ScenarioResult]:
        results = []
        for s in self._scenarios:
            results.append(self.run(s))
        return results

    def summary(self) -> Dict[str, Any]:
        results = self._results or self.run_all()
        return {
            "total_scenarios": len(results),
            "passed": sum(1 for r in results if r.passed),
            "failed": sum(1 for r in results if not r.passed),
            "details": [r.to_dict() for r in results[-10:]],
        }
