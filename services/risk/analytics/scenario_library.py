"""
Scenario Library — Built-in catalog of historical and macro-economic risk scenarios.

Provides a curated collection of pre-defined stress scenarios representing
major historical market events, crises, and macro-economic regimes.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class Scenario:
    """A risk scenario definition."""
    scenario_id: str
    name: str
    description: str
    category: str  # historical, macro, market_structure, custom
    severity: str  # mild, moderate, severe, extreme
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    asset_shocks: dict[str, float] = field(default_factory=dict)
    macro_variables: dict[str, float] = field(default_factory=dict)
    volatility_multiplier: float = 1.0
    correlation_changes: dict[str, float] = field(default_factory=dict)
    liquidity_discount: float = 0.0
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class ScenarioLibrary:
    """
    Curated library of historical and macro-economic risk scenarios.

    Contains built-in scenarios for major market events (2008 crisis,
    COVID crash, etc.) and supports user-defined custom scenarios.

    Usage::

        library = ScenarioLibrary()
        library.initialize()
        scenarios = library.get_by_tags(["equity", "crisis"])
    """

    BUILTIN_SCENARIOS: list[dict[str, Any]] = [
        {
            "scenario_id": "2008_gfc",
            "name": "2008 Global Financial Crisis",
            "description": "Lehman collapse, credit freeze, global equity crash",
            "category": "historical",
            "severity": "extreme",
            "start_date": date(2008, 9, 1),
            "end_date": date(2009, 3, 31),
            "asset_shocks": {"equity": -0.50, "credit": -0.35, "real_estate": -0.55, "commodity": -0.40},
            "macro_variables": {"gdp_growth": -3.0, "unemployment": 10.0, "vix": 80.0},
            "volatility_multiplier": 4.0,
            "correlation_changes": {"equity_equity": 0.85, "equity_bond": -0.30},
            "liquidity_discount": 0.30,
            "tags": ["equity", "credit", "global", "crisis", "systemic"],
        },
        {
            "scenario_id": "2020_covid",
            "name": "2020 COVID-19 Crash",
            "description": "Pandemic-driven global selloff and recovery",
            "category": "historical",
            "severity": "severe",
            "start_date": date(2020, 2, 19),
            "end_date": date(2020, 3, 23),
            "asset_shocks": {"equity": -0.34, "energy": -0.60, "travel": -0.65, "tech": -0.25},
            "macro_variables": {"gdp_growth": -5.0, "unemployment": 14.7, "vix": 82.0},
            "volatility_multiplier": 5.0,
            "liquidity_discount": 0.25,
            "tags": ["equity", "pandemic", "global", "volatility"],
        },
        {
            "scenario_id": "2022_inflation",
            "name": "2022 Inflation & Rate Shock",
            "description": "Inflation surge with aggressive Fed tightening",
            "category": "historical",
            "severity": "severe",
            "start_date": date(2022, 1, 1),
            "end_date": date(2022, 10, 31),
            "asset_shocks": {"bond": -0.15, "growth_stock": -0.40, "equity": -0.25, "crypto": -0.60},
            "macro_variables": {"cpi": 9.1, "fed_rate": 4.5, "real_yield": 2.0},
            "volatility_multiplier": 2.5,
            "correlation_changes": {"equity_bond": 0.60},
            "tags": ["rates", "inflation", "bond", "growth"],
        },
        {
            "scenario_id": "2010_flash_crash",
            "name": "2010 Flash Crash",
            "description": "Algorithmic trading-driven intraday crash",
            "category": "market_structure",
            "severity": "moderate",
            "start_date": date(2010, 5, 6),
            "end_date": date(2010, 5, 6),
            "asset_shocks": {"equity": -0.09, "futures": -0.09},
            "volatility_multiplier": 6.0,
            "liquidity_discount": 0.50,
            "tags": ["intraday", "liquidity", "algo", "equity"],
        },
        {
            "scenario_id": "2015_china_crash",
            "name": "2015 China Market Crash",
            "description": "Chinese equity bubble burst and circuit breaker",
            "category": "historical",
            "severity": "severe",
            "start_date": date(2015, 6, 12),
            "end_date": date(2015, 8, 26),
            "asset_shocks": {"china_equity": -0.45, "emerging_market": -0.30, "commodity": -0.25},
            "macro_variables": {"china_gdp": 6.8, "cny_usd": -0.05},
            "volatility_multiplier": 3.5,
            "tags": ["china", "emerging_market", "equity"],
        },
        {
            "scenario_id": "dotcom_burst",
            "name": "Dot-Com Bubble Burst",
            "description": "Tech bubble collapse 2000-2002",
            "category": "historical",
            "severity": "extreme",
            "start_date": date(2000, 3, 10),
            "end_date": date(2002, 10, 9),
            "asset_shocks": {"tech": -0.78, "equity": -0.49, "nasdaq": -0.78},
            "macro_variables": {"fed_rate": 1.75, "gdp_growth": 0.5},
            "volatility_multiplier": 2.0,
            "tags": ["tech", "bubble", "equity", "growth"],
        },
        {
            "scenario_id": "2018_vix_event",
            "name": "2018 Volmageddon",
            "description": "Short-volatility trade unwind",
            "category": "market_structure",
            "severity": "moderate",
            "start_date": date(2018, 2, 5),
            "end_date": date(2018, 2, 9),
            "asset_shocks": {"equity": -0.10, "volatility_products": -0.90},
            "volatility_multiplier": 8.0,
            "liquidity_discount": 0.15,
            "tags": ["volatility", "etp", "equity"],
        },
        {
            "scenario_id": "2011_euro_crisis",
            "name": "2011 Eurozone Debt Crisis",
            "description": "Sovereign debt crisis, Greece, contagion",
            "category": "historical",
            "severity": "severe",
            "start_date": date(2011, 7, 1),
            "end_date": date(2011, 12, 31),
            "asset_shocks": {"europe_equity": -0.35, "sovereign_bond": -0.20, "eur_usd": -0.12},
            "macro_variables": {"eurozone_gdp": -1.0, "italy_10y": 7.0},
            "volatility_multiplier": 3.0,
            "correlation_changes": {"peripheral_spread": 0.90},
            "tags": ["europe", "sovereign", "fx", "credit"],
        },
        {
            "scenario_id": "stagflation_70s",
            "name": "1970s Stagflation",
            "description": "High inflation + low growth regime",
            "category": "macro",
            "severity": "severe",
            "macro_variables": {"cpi": 12.0, "gdp_growth": -1.5, "unemployment": 8.0, "oil_price": 200},
            "asset_shocks": {"equity": -0.30, "bond": -0.20, "commodity": 0.50, "gold": 0.80},
            "volatility_multiplier": 2.0,
            "correlation_changes": {"equity_bond": 0.50},
            "tags": ["macro", "inflation", "commodity", "stagflation"],
        },
        {
            "scenario_id": "taper_tantrum_2013",
            "name": "2013 Taper Tantrum",
            "description": "Fed taper announcement, EM selloff",
            "category": "historical",
            "severity": "moderate",
            "start_date": date(2013, 5, 22),
            "end_date": date(2013, 6, 24),
            "asset_shocks": {"emerging_market": -0.15, "bond": -0.05, "em_fx": -0.10},
            "macro_variables": {"us_10y": 2.6, "em_outflows": 30},
            "volatility_multiplier": 1.8,
            "tags": ["fed", "emerging_market", "bond", "fx"],
        },
    ]

    def __init__(self) -> None:
        self._scenarios: dict[str, Scenario] = {}
        self._custom_scenarios: dict[str, Scenario] = {}
        self._initialized = False

    def initialize(self) -> None:
        """Load built-in scenarios."""
        if self._initialized:
            return
        for data in self.BUILTIN_SCENARIOS:
            scenario = Scenario(**data)
            self._scenarios[scenario.scenario_id] = scenario
        self._initialized = True
        logger.info(f"ScenarioLibrary: loaded {len(self._scenarios)} built-in scenarios.")

    # ---- Query ----

    def get(self, scenario_id: str) -> Optional[Scenario]:
        """Get a scenario by ID (checks built-in and custom)."""
        return self._scenarios.get(scenario_id) or self._custom_scenarios.get(scenario_id)

    def get_all(self) -> list[Scenario]:
        """Get all scenarios (built-in + custom)."""
        return list(self._scenarios.values()) + list(self._custom_scenarios.values())

    def get_builtin(self) -> list[Scenario]:
        """Get built-in scenarios only."""
        return list(self._scenarios.values())

    def get_custom(self) -> list[Scenario]:
        """Get custom scenarios only."""
        return list(self._custom_scenarios.values())

    def get_by_category(self, category: str) -> list[Scenario]:
        """Get scenarios by category."""
        all_scenarios = self.get_all()
        return [s for s in all_scenarios if s.category == category]

    def get_by_severity(self, severity: str) -> list[Scenario]:
        """Get scenarios by severity."""
        all_scenarios = self.get_all()
        return [s for s in all_scenarios if s.severity == severity]

    def get_by_tags(self, tags: list[str]) -> list[Scenario]:
        """Get scenarios matching any of the given tags."""
        all_scenarios = self.get_all()
        tag_set = set(tags)
        return [s for s in all_scenarios if tag_set.intersection(s.tags)]

    def search(self, keyword: str) -> list[Scenario]:
        """Search scenarios by keyword in name/description."""
        keyword_lower = keyword.lower()
        all_scenarios = self.get_all()
        return [
            s for s in all_scenarios
            if keyword_lower in s.name.lower() or keyword_lower in s.description.lower()
        ]

    # ---- Custom Scenario Management ----

    def add_custom(self, scenario: Scenario) -> None:
        """Add a custom scenario."""
        self._custom_scenarios[scenario.scenario_id] = scenario
        logger.info(f"ScenarioLibrary: added custom scenario '{scenario.scenario_id}'.")

    def update_custom(self, scenario: Scenario) -> None:
        """Update a custom scenario."""
        self._custom_scenarios[scenario.scenario_id] = scenario
        logger.info(f"ScenarioLibrary: updated custom scenario '{scenario.scenario_id}'.")

    def remove_custom(self, scenario_id: str) -> bool:
        """Remove a custom scenario."""
        if scenario_id in self._custom_scenarios:
            del self._custom_scenarios[scenario_id]
            return True
        return False

    def count(self) -> int:
        """Total number of scenarios."""
        return len(self._scenarios) + len(self._custom_scenarios)
