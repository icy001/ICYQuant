"""Scenario Simulator – predefined and custom scenario library."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Scenario:
    """A predefined risk scenario for stress testing and simulation."""

    name: str
    category: str  # "market_crash", "liquidity", "sector", "volatility", "macro"
    description: str
    price_shock: float
    correlation_amplification: float = 0.0
    liquidity_discount: float = 0.0
    volatility_spike: float = 0.0
    params: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "category": self.category,
            "description": self.description,
            "price_shock": self.price_shock,
            "correlation_amplification": self.correlation_amplification,
            "liquidity_discount": self.liquidity_discount,
            "volatility_spike": self.volatility_spike,
            "params": self.params,
        }


# Predefined scenario library
DEFAULT_SCENARIOS: List[Scenario] = [
    Scenario(
        name="Market Crash",
        category="market_crash",
        description="Broad market decline similar to 2008 or 2020",
        price_shock=-0.30,
        correlation_amplification=0.5,
        liquidity_discount=0.05,
        volatility_spike=0.6,
    ),
    Scenario(
        name="Liquidity Crisis",
        category="liquidity",
        description="Severe liquidity dry-up with forced selling",
        price_shock=-0.15,
        correlation_amplification=0.3,
        liquidity_discount=0.15,
        volatility_spike=0.4,
    ),
    Scenario(
        name="Sector Rotation",
        category="sector",
        description="Rapid rotation out of growth into value sectors",
        price_shock=-0.12,
        correlation_amplification=0.2,
        liquidity_discount=0.02,
        volatility_spike=0.25,
    ),
    Scenario(
        name="Volatility Spike",
        category="volatility",
        description="VIX surge with cross-asset vol expansion",
        price_shock=-0.08,
        correlation_amplification=0.4,
        liquidity_discount=0.03,
        volatility_spike=0.5,
    ),
    Scenario(
        name="Macro Shock",
        category="macro",
        description="Unexpected rate hike or geopolitical event",
        price_shock=-0.20,
        correlation_amplification=0.35,
        liquidity_discount=0.08,
        volatility_spike=0.45,
    ),
    Scenario(
        name="Tech Correction",
        category="sector",
        description="Technology sector-specific sell-off",
        price_shock=-0.25,
        correlation_amplification=0.3,
        liquidity_discount=0.04,
        volatility_spike=0.35,
    ),
    Scenario(
        name="Currency Shock",
        category="macro",
        description="Sharp currency devaluation / appreciation",
        price_shock=-0.10,
        correlation_amplification=0.15,
        liquidity_discount=0.02,
        volatility_spike=0.3,
    ),
]


class ScenarioSimulator:
    """Manages and runs risk scenarios from a customizable library.

    Supports predefined institutional-grade scenarios and custom
    user-defined scenarios for stress testing portfolios.
    """

    def __init__(self, scenarios: Optional[List[Scenario]] = None):
        self.scenarios = scenarios or [s for s in DEFAULT_SCENARIOS]

    def get_scenario(self, name: str) -> Optional[Scenario]:
        """Find a scenario by name (case-insensitive)."""
        for s in self.scenarios:
            if s.name.lower() == name.lower():
                return s
        return None

    def by_category(self, category: str) -> List[Scenario]:
        """Return all scenarios in a given category."""
        return [s for s in self.scenarios if s.category == category]

    def categories(self) -> List[str]:
        """Return list of available scenario categories."""
        return list({s.category for s in self.scenarios})

    def add_scenario(self, scenario: Scenario) -> None:
        """Add a custom scenario to the library."""
        self.scenarios.append(scenario)

    def simulate(self, event: str) -> dict:
        """Simulate a named event and return its scenario parameters.

        If the event matches a predefined scenario, return its details.
        Otherwise, return a generic representation.
        """
        scenario = self.get_scenario(event)
        if scenario:
            return {
                "event": event,
                "matched": True,
                "scenario": scenario.to_dict(),
            }
        return {"event": event, "matched": False}

    def simulate_all(
        self, portfolio_value: float = 1_000_000.0
    ) -> List[Dict[str, Any]]:
        """Return all scenarios with their simulation parameters."""
        results: List[Dict[str, Any]] = []
        for s in self.scenarios:
            results.append({
                "event": s.name,
                "matched": True,
                "scenario": s.to_dict(),
                "portfolio_value": portfolio_value,
            })
        return results
