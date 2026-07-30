"""ICYQuant Scenario Engine.

Manages and generates stress test scenarios including historical
replays, hypothetical shocks, and regulatory scenarios.

Usage::

    engine = ScenarioEngine(ScenarioEngineConfig())
    scenarios = engine.get_predefined_scenarios()
    custom = engine.create_custom_scenario("Trade War", shocks)
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from services.risk_intelligence.config import (
    ScenarioEngineConfig,
)
from services.risk_intelligence.stress_testing import StressScenario


# ============================================================================
# Predefined Scenarios
# ============================================================================

PREDEFINED_SCENARIOS: Dict[str, Dict[str, Any]] = {
    "COVID2020": {
        "description": "COVID-19 market crash (Feb-Mar 2020)",
        "shocks": {
            "SPX": -0.34,
            "NASDAQ": -0.30,
            "DJI": -0.37,
            "OIL": -0.50,
            "VIX": 4.0,
            "EM": -0.38,
            "CREDIT": -0.25,
            "REITS": -0.42,
        },
        "duration_days": 22,
    },
    "GFC2008": {
        "description": "Global Financial Crisis (Sep-Oct 2008)",
        "shocks": {
            "SPX": -0.47,
            "NASDAQ": -0.47,
            "DJI": -0.46,
            "BANKS": -0.65,
            "REITS": -0.70,
            "EM": -0.55,
            "CREDIT": -0.40,
        },
        "duration_days": 40,
    },
    "Fed2022": {
        "description": "Fed rate hiking cycle (2022)",
        "shocks": {
            "SPX": -0.20,
            "NASDAQ": -0.33,
            "BONDS_2Y": -0.10,
            "BONDS_10Y": -0.15,
            "CRYPTO": -0.60,
            "TECH": -0.35,
        },
        "duration_days": 60,
    },
    "taper_tantrum": {
        "description": "2013 Taper Tantrum",
        "shocks": {
            "EM": -0.20,
            "BONDS_10Y": -0.12,
            "EM_CURRENCY": -0.15,
        },
        "duration_days": 15,
    },
    "volatility_crisis": {
        "description": "2018 Volmageddon (Volatility ETPs)",
        "shocks": {
            "SPX": -0.10,
            "VIX": 3.0,
            "SHORT_VOL": -0.90,
        },
        "duration_days": 5,
    },
    "oil_crash": {
        "description": "Oil price crash scenario",
        "shocks": {
            "OIL": -0.40,
            "ENERGY": -0.35,
            "HIGH_YIELD": -0.20,
            "OIL_PRODUCERS": -0.50,
        },
        "duration_days": 30,
    },
    "china_crash": {
        "description": "China market stress",
        "shocks": {
            "CSI300": -0.30,
            "HSCEI": -0.25,
            "CNH": -0.10,
            "EM": -0.20,
            "COPPER": -0.15,
        },
        "duration_days": 20,
    },
    "liquidity_crisis": {
        "description": "System-wide liquidity freeze",
        "shocks": {
            "SPX": -0.25,
            "HY_CREDIT": -0.35,
            "IG_CREDIT": -0.15,
            "FUNDING": 5.0,
            "REPO": 10.0,
        },
        "duration_days": 10,
    },
    "brexit": {
        "description": "Brexit-style referendum shock",
        "shocks": {
            "GBP": -0.10,
            "FTSE100": -0.08,
            "FTSE250": -0.14,
            "UK_BANKS": -0.20,
        },
        "duration_days": 5,
    },
    "pandemic_contained": {
        "description": "Contained pandemic recovery",
        "shocks": {
            "TRAVEL": -0.20,
            "HOSPITALITY": -0.15,
            "OIL": -0.10,
            "HEALTHCARE": 0.05,
            "TECH": 0.05,
        },
        "duration_days": 14,
    },
}


# ============================================================================
# Scenario Engine
# ============================================================================


class ScenarioEngine:
    """Stress Scenario Engine.

    Creates and manages scenarios for stress testing.
    Includes predefined historical events and supports custom scenarios.

    Usage::

        engine = ScenarioEngine(ScenarioEngineConfig())
        covid_scenario = engine.get_scenario("COVID2020")
        custom = engine.create_custom_scenario("My Scenario", shocks)
    """

    def __init__(self, config: Optional[ScenarioEngineConfig] = None) -> None:
        self.config = config or ScenarioEngineConfig()
        self._custom_scenarios: Dict[str, StressScenario] = {}
        self._scenarios: Dict[str, StressScenario] = {}
        self._init_predefined_scenarios()

    def _init_predefined_scenarios(self) -> None:
        """Initialize predefined historical scenarios."""
        for name, data in PREDEFINED_SCENARIOS.items():
            self._scenarios[name] = StressScenario(
                name=name,
                scenario_type=data.get("scenario_type", "historical"),
                description=data["description"],
                shocks=data["shocks"],
                duration_days=data.get("duration_days", 10),
                metadata={"predefined": True},
            )

    # ------------------------------------------------------------------
    # Scenario Management
    # ------------------------------------------------------------------

    def get_scenario(self, name: str) -> Optional[StressScenario]:
        """Get a scenario by name (predefined + custom)."""
        return self._scenarios.get(name) or self._custom_scenarios.get(name)

    def list_scenarios(
        self, scenario_type: Optional[str] = None,
    ) -> List[StressScenario]:
        """List all available scenarios, optionally filtered by type."""
        all_scenarios = list(self._scenarios.values()) + list(
            self._custom_scenarios.values()
        )
        if scenario_type:
            all_scenarios = [
                s for s in all_scenarios
                if s.scenario_type.value == scenario_type
            ]
        return all_scenarios

    def get_predefined_scenarios(self) -> List[StressScenario]:
        """Get all predefined scenarios."""
        return list(self._scenarios.values())

    def get_custom_scenarios(self) -> List[StressScenario]:
        """Get all user-created custom scenarios."""
        return list(self._custom_scenarios.values())

    # ------------------------------------------------------------------
    # Scenario Creation
    # ------------------------------------------------------------------

    def create_custom_scenario(
        self,
        name: str,
        shocks: Dict[str, float],
        description: str = "",
        correlations: Optional[Dict[str, float]] = None,
        duration_days: int = 10,
    ) -> StressScenario:
        """Create a custom stress scenario.

        Args:
            name: Unique scenario name.
            shocks: {asset: shock_pct} e.g. {"SPX": -0.20}.
            description: Human-readable description.
            correlations: Optional correlation adjustments.
            duration_days: Scenario horizon.

        Returns:
            New StressScenario instance.
        """
        if len(self._custom_scenarios) >= self.config.max_scenarios:
            oldest = min(
                self._custom_scenarios.keys(),
                key=lambda k: self._custom_scenarios[k].metadata.get(
                    "created_at", datetime.min
                ),
            )
            del self._custom_scenarios[oldest]

        scenario = StressScenario(
            name=name,
            scenario_type="hypothetical",
            description=description,
            shocks=shocks,
            correlations=correlations,
            duration_days=duration_days,
            metadata={
                "custom": True,
                "created_at": datetime.utcnow(),
            },
        )

        self._custom_scenarios[name] = scenario
        return scenario

    def combine_scenarios(
        self,
        name: str,
        scenario_names: List[str],
        weight: Optional[List[float]] = None,
    ) -> StressScenario:
        """Combine multiple scenarios with weights.

        Args:
            name: Name for the combined scenario.
            scenario_names: Names of scenarios to combine.
            weight: Optional weights for each scenario.

        Returns:
            Combined StressScenario.
        """
        combined_shocks: Dict[str, float] = {}
        all_descriptions: List[str] = []
        total_duration = 0

        if weight is None:
            weight = [1.0 / len(scenario_names)] * len(scenario_names)

        for i, sname in enumerate(scenario_names):
            scenario = self.get_scenario(sname)
            if scenario is None:
                continue

            w = weight[i] if i < len(weight) else 1.0 / len(scenario_names)
            all_descriptions.append(scenario.description)
            total_duration += int(scenario.duration_days * w)

            for asset, shock in scenario.shocks.items():
                if asset not in combined_shocks:
                    combined_shocks[asset] = 0.0
                combined_shocks[asset] += shock * w

        return StressScenario(
            name=name,
            scenario_type="hypothetical",
            description="Combined: " + " + ".join(all_descriptions),
            shocks=combined_shocks,
            duration_days=max(1, total_duration),
            metadata={
                "combined": True,
                "sources": scenario_names,
                "weights": weight,
                "created_at": datetime.utcnow(),
            },
        )

    # ------------------------------------------------------------------
    # Scenario Analysis
    # ------------------------------------------------------------------

    def get_worst_scenario(
        self,
        positions: Dict[str, float],
        scenario_names: Optional[List[str]] = None,
    ) -> Optional[StressScenario]:
        """Find the worst scenario for given positions.

        Args:
            positions: {asset: weight} mapping.
            scenario_names: Subset of scenarios to check.

        Returns:
            Worst StressScenario or None.
        """
        scenarios = self._scenarios.copy()
        scenarios.update(self._custom_scenarios)

        if scenario_names:
            scenarios = {
                k: v for k, v in scenarios.items() if k in scenario_names
            }

        worst = None
        worst_loss = float("inf")

        for scenario in scenarios.values():
            loss = 0.0
            for asset, weight in positions.items():
                shock = scenario.shocks.get(asset, 0.0)
                loss += weight * shock

            if loss < worst_loss:
                worst_loss = loss
                worst = scenario

        return worst

    def delete_scenario(self, name: str) -> bool:
        """Delete a custom scenario. Predefined scenarios cannot be deleted."""
        if name in self._scenarios:
            return False
        if name in self._custom_scenarios:
            del self._custom_scenarios[name]
            return True
        return False

    def scenario_count(self) -> Dict[str, int]:
        """Get count of scenarios by type."""
        return {
            "predefined": len(self._scenarios),
            "custom": len(self._custom_scenarios),
            "total": len(self._scenarios) + len(self._custom_scenarios),
        }
