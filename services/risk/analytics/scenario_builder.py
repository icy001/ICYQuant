"""
Scenario Builder — Interactive builder for custom risk scenarios.

Provides a fluent API to construct custom stress testing scenarios
with multi-asset shocks, macro variables, and volatility adjustments.
"""

from __future__ import annotations

import logging
import uuid
from datetime import date
from typing import Any, Optional

from .scenario_library import Scenario

logger = logging.getLogger(__name__)


class ScenarioBuilder:
    """
    Fluent builder for constructing custom risk scenarios.

    Usage::

        builder = ScenarioBuilder()
        scenario = (
            builder
            .with_id("my_custom_crash")
            .with_name("Custom Market Crash")
            .with_description("My custom crash scenario")
            .with_category("custom")
            .with_severity("severe")
            .with_equity_shock(-0.30)
            .with_bond_shock(-0.10)
            .with_volatility_multiplier(3.0)
            .with_liquidity_discount(0.20)
            .with_tag("custom")
            .with_tag("equity")
            .build()
        )
    """

    def __init__(self) -> None:
        self._scenario_id: str = ""
        self._name: str = ""
        self._description: str = ""
        self._category: str = "custom"
        self._severity: str = "moderate"
        self._start_date: Optional[date] = None
        self._end_date: Optional[date] = None
        self._asset_shocks: dict[str, float] = {}
        self._macro_variables: dict[str, float] = {}
        self._volatility_multiplier: float = 1.0
        self._correlation_changes: dict[str, float] = {}
        self._liquidity_discount: float = 0.0
        self._tags: list[str] = []
        self._metadata: dict[str, Any] = {}

    def with_id(self, scenario_id: str) -> "ScenarioBuilder":
        self._scenario_id = scenario_id
        return self

    def with_name(self, name: str) -> "ScenarioBuilder":
        self._name = name
        return self

    def with_description(self, description: str) -> "ScenarioBuilder":
        self._description = description
        return self

    def with_category(self, category: str) -> "ScenarioBuilder":
        self._category = category
        return self

    def with_severity(self, severity: str) -> "ScenarioBuilder":
        self._severity = severity
        return self

    def with_start_date(self, start_date: date) -> "ScenarioBuilder":
        self._start_date = start_date
        return self

    def with_end_date(self, end_date: date) -> "ScenarioBuilder":
        self._end_date = end_date
        return self

    # ---- Asset Shocks ----

    def with_shock(self, asset: str, shock_pct: float) -> "ScenarioBuilder":
        """Add a price shock for a specific asset or asset class.

        shock_pct should be between -1.0 and +1.0 (e.g., -0.30 = -30%).
        """
        self._asset_shocks[asset] = shock_pct
        return self

    def with_equity_shock(self, pct: float) -> "ScenarioBuilder":
        return self.with_shock("equity", pct)

    def with_bond_shock(self, pct: float) -> "ScenarioBuilder":
        return self.with_shock("bond", pct)

    def with_commodity_shock(self, pct: float) -> "ScenarioBuilder":
        return self.with_shock("commodity", pct)

    def with_forex_shock(self, pct: float) -> "ScenarioBuilder":
        return self.with_shock("forex", pct)

    def with_credit_shock(self, pct: float) -> "ScenarioBuilder":
        return self.with_shock("credit", pct)

    def with_real_estate_shock(self, pct: float) -> "ScenarioBuilder":
        return self.with_shock("real_estate", pct)

    def with_crypto_shock(self, pct: float) -> "ScenarioBuilder":
        return self.with_shock("crypto", pct)

    def with_broad_market_shock(self, pct: float) -> "ScenarioBuilder":
        return self.with_shock("*", pct)

    # ---- Macro Variables ----

    def with_macro(self, variable: str, value: float) -> "ScenarioBuilder":
        """Add a macro-economic variable."""
        self._macro_variables[variable] = value
        return self

    def with_gdp(self, growth_pct: float) -> "ScenarioBuilder":
        return self.with_macro("gdp_growth", growth_pct)

    def with_inflation(self, cpi: float) -> "ScenarioBuilder":
        return self.with_macro("cpi", cpi)

    def with_unemployment(self, rate: float) -> "ScenarioBuilder":
        return self.with_macro("unemployment", rate)

    def with_interest_rate(self, rate: float) -> "ScenarioBuilder":
        return self.with_macro("fed_rate", rate)

    def with_vix(self, level: float) -> "ScenarioBuilder":
        return self.with_macro("vix", level)

    def with_oil_price(self, price: float) -> "ScenarioBuilder":
        return self.with_macro("oil_price", price)

    # ---- Market Conditions ----

    def with_volatility_multiplier(self, multiplier: float) -> "ScenarioBuilder":
        """Set volatility multiplier (1.0 = normal, 3.0 = 3x volatility)."""
        self._volatility_multiplier = multiplier
        return self

    def with_liquidity_discount(self, discount: float) -> "ScenarioBuilder":
        """Set liquidity discount (0.0 = full liquidity, 0.3 = 30% haircut)."""
        self._liquidity_discount = discount
        return self

    def with_correlation_change(self, pair: str, value: float) -> "ScenarioBuilder":
        """Set a correlation change (e.g., 'equity_bond': 0.60)."""
        self._correlation_changes[pair] = value
        return self

    # ---- Metadata ----

    def with_tag(self, tag: str) -> "ScenarioBuilder":
        self._tags.append(tag)
        return self

    def with_tags(self, tags: list[str]) -> "ScenarioBuilder":
        self._tags.extend(tags)
        return self

    def with_metadata(self, key: str, value: Any) -> "ScenarioBuilder":
        self._metadata[key] = value
        return self

    # ---- Build ----

    def build(self) -> Scenario:
        """Build and return the scenario."""
        if not self._scenario_id:
            self._scenario_id = f"custom_{uuid.uuid4().hex[:8]}"
        if not self._name:
            self._name = self._scenario_id

        return Scenario(
            scenario_id=self._scenario_id,
            name=self._name,
            description=self._description,
            category=self._category,
            severity=self._severity,
            start_date=self._start_date,
            end_date=self._end_date,
            asset_shocks=dict(self._asset_shocks),
            macro_variables=dict(self._macro_variables),
            volatility_multiplier=self._volatility_multiplier,
            correlation_changes=dict(self._correlation_changes),
            liquidity_discount=self._liquidity_discount,
            tags=list(self._tags),
            metadata=dict(self._metadata),
        )

    @classmethod
    def from_scenario(cls, scenario: Scenario) -> "ScenarioBuilder":
        """Create a builder pre-populated from an existing scenario."""
        builder = cls()
        builder._scenario_id = scenario.scenario_id
        builder._name = scenario.name
        builder._description = scenario.description
        builder._category = scenario.category
        builder._severity = scenario.severity
        builder._start_date = scenario.start_date
        builder._end_date = scenario.end_date
        builder._asset_shocks = dict(scenario.asset_shocks)
        builder._macro_variables = dict(scenario.macro_variables)
        builder._volatility_multiplier = scenario.volatility_multiplier
        builder._correlation_changes = dict(scenario.correlation_changes)
        builder._liquidity_discount = scenario.liquidity_discount
        builder._tags = list(scenario.tags)
        builder._metadata = dict(scenario.metadata)
        return builder

    def reset(self) -> None:
        """Reset all fields to defaults."""
        self.__init__()
