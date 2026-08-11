"""StressScenario — scenario definition and management.

Defines, stores, and manages stress scenarios including
historical event recreations and hypothetical "what-if"s.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional


class ScenarioSeverity(Enum):
    """Scenario severity levels."""

    MODERATE = auto()
    SEVERE = auto()
    EXTREME = auto()
    HISTORICAL = auto()
    CUSTOM = auto()


@dataclass
class ScenarioDefinition:
    """Complete stress scenario definition."""

    scenario_id: str
    name: str
    severity: ScenarioSeverity = ScenarioSeverity.SEVERE
    description: str = ""

    # shocks
    market_shock: float = 0.0
    volatility_shock: float = 0.0
    liquidity_shock: float = 0.0
    correlation_shock: float = 0.0
    spread_shock: float = 0.0
    gap_shock: float = 0.0
    execution_shock: float = 0.0

    # factor-specific
    factor_shocks: Dict[str, float] = field(default_factory=dict)
    sector_shocks: Dict[str, float] = field(default_factory=dict)

    # duration
    shock_duration_days: int = 1

    # probability
    annual_probability: float = 0.01  # 1-in-100 year

    # reference
    historical_reference: Optional[str] = None

    # tags
    tags: List[str] = field(default_factory=list)


class StressScenarioLibrary:
    """Library of predefined and custom stress scenarios.

    Includes recreations of historical events like 2008, 2020 COVID,
    and hypothetical scenarios for forward-looking stress testing.

    Usage::

        library = StressScenarioLibrary()
        covid = library.get("covid_2020")
        custom = library.create_custom("my_scenario", market_shock=-25.0)
    """

    def __init__(self):
        self._scenarios: Dict[str, ScenarioDefinition] = {}
        self._register_defaults()

    def _register_defaults(self) -> None:
        """Register default historical and hypothetical scenarios."""

        defaults = [
            ScenarioDefinition(
                scenario_id="covid_2020",
                name="COVID-19 Crash (2020)",
                severity=ScenarioSeverity.HISTORICAL,
                description="Recreation of March 2020 COVID market crash",
                market_shock=-34.0,
                volatility_shock=200.0,
                liquidity_shock=-40.0,
                correlation_shock=30.0,
                spread_shock=100.0,
                historical_reference="COVID-19 March 2020",
                annual_probability=0.05,
                tags=["historical", "pandemic", "crash"],
            ),
            ScenarioDefinition(
                scenario_id="gfc_2008",
                name="Global Financial Crisis (2008)",
                severity=ScenarioSeverity.EXTREME,
                description="Recreation of 2008 GFC",
                market_shock=-57.0,
                volatility_shock=300.0,
                liquidity_shock=-70.0,
                correlation_shock=60.0,
                spread_shock=300.0,
                gap_shock=-15.0,
                historical_reference="2008 GFC",
                annual_probability=0.02,
                tags=["historical", "financial_crisis", "systemic"],
            ),
            ScenarioDefinition(
                scenario_id="flash_crash",
                name="Flash Crash",
                severity=ScenarioSeverity.SEVERE,
                description="Sudden intraday crash with rapid recovery",
                market_shock=-10.0,
                volatility_shock=150.0,
                liquidity_shock=-80.0,
                execution_shock=-50.0,
                shock_duration_days=1,
                annual_probability=0.03,
                tags=["historical", "flash_crash", "liquidity"],
            ),
            ScenarioDefinition(
                scenario_id="rate_hike",
                name="Aggressive Rate Hike",
                severity=ScenarioSeverity.MODERATE,
                description="Central bank aggressive tightening",
                market_shock=-8.0,
                volatility_shock=40.0,
                spread_shock=50.0,
                factor_shocks={"Rates": 25.0, "USD": 10.0},
                annual_probability=0.10,
                tags=["monetary", "rates", "tightening"],
            ),
            ScenarioDefinition(
                scenario_id="tech_crash",
                name="Tech Sector Crash",
                severity=ScenarioSeverity.SEVERE,
                description="Technology sector-specific crash",
                market_shock=-5.0,
                factor_shocks={"Tech": -30.0, "AI": -35.0, "Growth": -25.0},
                sector_shocks={"Technology": -25.0},
                annual_probability=0.08,
                tags=["sector", "tech", "concentration"],
            ),
            ScenarioDefinition(
                scenario_id="correlation_one",
                name="Correlation → 1.0",
                severity=ScenarioSeverity.EXTREME,
                description="All correlations converge to 1 — zero diversification",
                correlation_shock=80.0,
                volatility_shock=60.0,
                market_shock=-20.0,
                liquidity_shock=-40.0,
                annual_probability=0.02,
                tags=["correlation", "diversification", "systemic"],
            ),
            ScenarioDefinition(
                scenario_id="volmageddon",
                name="Volmageddon",
                severity=ScenarioSeverity.EXTREME,
                description="Volatility explosion (Feb 2018 style)",
                market_shock=-15.0,
                volatility_shock=400.0,
                correlation_shock=20.0,
                annual_probability=0.03,
                tags=["volatility", "volmageddon", "tail"],
            ),
        ]

        for s in defaults:
            self._scenarios[s.scenario_id] = s

    def get(self, scenario_id: str) -> Optional[ScenarioDefinition]:
        """Get a scenario by ID."""
        return self._scenarios.get(scenario_id)

    def list_all(self) -> List[ScenarioDefinition]:
        """List all registered scenarios."""
        return list(self._scenarios.values())

    def list_by_severity(self, severity: ScenarioSeverity) -> List[ScenarioDefinition]:
        """List scenarios by severity."""
        return [s for s in self._scenarios.values() if s.severity == severity]

    def list_by_tag(self, tag: str) -> List[ScenarioDefinition]:
        """List scenarios by tag."""
        return [s for s in self._scenarios.values() if tag in s.tags]

    def create_custom(
        self,
        name: str,
        scenario_id: Optional[str] = None,
        severity: ScenarioSeverity = ScenarioSeverity.CUSTOM,
        **shocks,
    ) -> ScenarioDefinition:
        """Create a custom scenario.

        Args:
            name: scenario name
            scenario_id: optional custom id (auto-generated if not provided)
            severity: scenario severity
            **shocks: any shock parameters (market_shock, volatility_shock, etc.)
        """
        sid = scenario_id or f"custom_{name.lower().replace(' ', '_')}"
        scenario = ScenarioDefinition(
            scenario_id=sid,
            name=name,
            severity=severity,
            **shocks,
        )
        self._scenarios[sid] = scenario
        return scenario

    def remove(self, scenario_id: str) -> bool:
        """Remove a scenario."""
        if scenario_id in self._scenarios:
            del self._scenarios[scenario_id]
            return True
        return False
