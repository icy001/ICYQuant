"""Stress Testing Framework - scenario definitions and management."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


class ScenarioEngine:
    """Stress test scenario definition and management engine.

    Provides predefined stress scenarios:
    - Market crash (S&P -10%)
    - Liquidity crisis (bid-ask spread ×3)
    - Sector shock (Semiconductor -20%)
    - Volatility spike
    - Correlation breakdown
    """

    # Predefined scenarios
    SCENARIOS: Dict[str, dict] = {
        "market_crash": {
            "name": "Market Crash",
            "description": "S&P 500 drops 10% in a single day",
            "severity": "SEVERE",
            "market_shock": {
                "equity": -0.10,
                "tech": -0.12,
                "finance": -0.08,
                "energy": -0.09,
                "consumer": -0.07,
            },
            "volatility_multiplier": 3.0,
            "correlation_shift": 0.3,
            "liquidity_discount": 0.05,
            "duration_days": 1,
        },
        "liquidity_crisis": {
            "name": "Liquidity Crisis",
            "description": "Bid-ask spreads widen 3x, liquidity dries up",
            "severity": "SEVERE",
            "market_shock": {
                "equity": -0.05,
                "small_cap": -0.10,
                "emerging_market": -0.08,
            },
            "volatility_multiplier": 2.0,
            "correlation_shift": 0.2,
            "liquidity_discount": 0.15,
            "duration_days": 3,
        },
        "sector_shock": {
            "name": "Semiconductor Sector Shock",
            "description": "Tech sector drops 20% on AI bubble concerns",
            "severity": "MODERATE",
            "market_shock": {
                "semiconductor": -0.20,
                "tech": -0.12,
                "hardware": -0.15,
                "equity": -0.04,
            },
            "volatility_multiplier": 2.0,
            "correlation_shift": 0.15,
            "liquidity_discount": 0.03,
            "duration_days": 5,
        },
        "volatility_spike": {
            "name": "Volatility Spike",
            "description": "VIX spikes to 40+, volatility regime change",
            "severity": "MODERATE",
            "market_shock": {
                "equity": -0.03,
                "options": -0.08,
            },
            "volatility_multiplier": 5.0,
            "correlation_shift": 0.1,
            "liquidity_discount": 0.02,
            "duration_days": 1,
        },
        "correlation_breakdown": {
            "name": "Correlation Breakdown",
            "description": "Cross-asset correlations break down",
            "severity": "MODERATE",
            "market_shock": {
                "equity": -0.02,
                "bonds": -0.01,
                "commodities": -0.05,
            },
            "volatility_multiplier": 1.5,
            "correlation_shift": -0.4,
            "liquidity_discount": 0.02,
            "duration_days": 1,
        },
        "interest_rate_shock": {
            "name": "Interest Rate Shock",
            "description": "Fed unexpectedly raises rates 100bps",
            "severity": "SEVERE",
            "market_shock": {
                "bonds": -0.05,
                "equity": -0.06,
                "real_estate": -0.10,
                "growth_stocks": -0.12,
                "value_stocks": -0.03,
            },
            "volatility_multiplier": 2.5,
            "correlation_shift": 0.25,
            "liquidity_discount": 0.05,
            "duration_days": 3,
        },
        "currency_crisis": {
            "name": "Currency Crisis",
            "description": "Major currency devaluation 15%",
            "severity": "MODERATE",
            "market_shock": {
                "fx": -0.15,
                "emerging_market": -0.10,
                "commodities": 0.05,
                "equity": -0.03,
            },
            "volatility_multiplier": 2.0,
            "correlation_shift": 0.1,
            "liquidity_discount": 0.03,
            "duration_days": 5,
        },
        "credit_crunch": {
            "name": "Credit Crunch",
            "description": "Credit markets freeze, spreads blow out",
            "severity": "SEVERE",
            "market_shock": {
                "corporate_bonds": -0.08,
                "high_yield": -0.15,
                "equity": -0.08,
                "finance": -0.12,
            },
            "volatility_multiplier": 3.0,
            "correlation_shift": 0.35,
            "liquidity_discount": 0.12,
            "duration_days": 10,
        },
    }

    def get_scenario(self, name: str) -> Optional[dict]:
        """Get a predefined scenario by name.

        Args:
            name: Scenario identifier.

        Returns:
            Scenario definition dict or None.
        """
        return self.SCENARIOS.get(name)

    def list_scenarios(self) -> List[str]:
        """List all available stress scenario names."""
        return list(self.SCENARIOS.keys())

    def get_scenarios_by_severity(self, severity: str) -> List[dict]:
        """Get all scenarios matching a severity level.

        Args:
            severity: "MILD", "MODERATE", "SEVERE", or "EXTREME".

        Returns:
            List of matching scenario dicts.
        """
        return [
            s for s in self.SCENARIOS.values()
            if s.get("severity", "").upper() == severity.upper()
        ]

    def define_custom_scenario(
        self,
        name: str,
        description: str,
        severity: str,
        market_shock: Dict[str, float],
        volatility_multiplier: float = 1.0,
        correlation_shift: float = 0.0,
        liquidity_discount: float = 0.0,
        duration_days: int = 1,
    ) -> dict:
        """Define a custom stress scenario.

        Args:
            name: Scenario name.
            description: Scenario description.
            severity: Severity level.
            market_shock: Asset -> shock % map.
            volatility_multiplier: Volatility increase factor.
            correlation_shift: Correlation change.
            liquidity_discount: Liquidity discount factor.
            duration_days: Scenario duration in days.

        Returns:
            The created scenario dict.
        """
        scenario = {
            "name": name,
            "description": description,
            "severity": severity,
            "market_shock": market_shock,
            "volatility_multiplier": volatility_multiplier,
            "correlation_shift": correlation_shift,
            "liquidity_discount": liquidity_discount,
            "duration_days": duration_days,
        }
        self.SCENARIOS[name.lower().replace(" ", "_")] = scenario
        return scenario

    def merge_scenarios(
        self,
        scenario_names: List[str],
        merge_name: str = "combined_scenario",
    ) -> Optional[dict]:
        """Combine multiple scenarios into a compound scenario.

        Args:
            scenario_names: List of scenario names to combine.
            merge_name: Name for the combined scenario.

        Returns:
            Combined scenario dict or None.
        """
        scenarios = [self.get_scenario(n) for n in scenario_names]
        scenarios = [s for s in scenarios if s is not None]
        if not scenarios:
            return None

        combined_shock = {}
        max_vol_mult = 1.0
        max_corr_shift = 0.0
        max_liq_disc = 0.0
        max_severity = "MILD"
        max_duration = 1

        severity_rank = {"MILD": 1, "MODERATE": 2, "SEVERE": 3, "EXTREME": 4}

        for s in scenarios:
            for asset, shock in s["market_shock"].items():
                combined_shock[asset] = combined_shock.get(asset, 0) + shock
            max_vol_mult = max(max_vol_mult, s["volatility_multiplier"])
            max_corr_shift = max(max_corr_shift, abs(s["correlation_shift"]))
            max_liq_disc = max(max_liq_disc, s["liquidity_discount"])
            max_duration = max(max_duration, s["duration_days"])
            if severity_rank.get(s["severity"], 1) > severity_rank.get(max_severity, 1):
                max_severity = s["severity"]

        combined = self.define_custom_scenario(
            name=merge_name,
            description=f"Combined: {', '.join(s['description'][:30] for s in scenarios)}",
            severity=max_severity,
            market_shock=combined_shock,
            volatility_multiplier=max_vol_mult,
            correlation_shift=max_corr_shift,
            liquidity_discount=max_liq_disc,
            duration_days=max_duration,
        )
        return combined
