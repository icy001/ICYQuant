"""
Liquidity Scenario — Defines and executes what-if liquidity scenarios.

Templates for common liquidity deterioration patterns:
- Volume decline scenarios
- Spread widening scenarios
- Combined multi-factor scenarios
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from .liquidity_profile import LiquidityProfile


class ScenarioType(str, Enum):
    VOLUME_DECLINE = "volume_decline"
    SPREAD_WIDENING = "spread_widening"
    DEPTH_REDUCTION = "depth_reduction"
    VOLATILITY_SPIKE = "volatility_spike"
    TURNOVER_COLLAPSE = "turnover_collapse"
    COMBINED = "combined"
    CUSTOM = "custom"


class ScenarioSeverity(str, Enum):
    MILD = "mild"
    MODERATE = "moderate"
    SEVERE = "severe"
    EXTREME = "extreme"


@dataclass
class LiquidityScenario:
    """A reusable liquidity scenario template."""

    scenario_id: str = field(default_factory=lambda: f"LS-{uuid.uuid4().hex[:8]}")
    name: str = ""
    description: str = ""
    scenario_type: ScenarioType = ScenarioType.CUSTOM
    severity: ScenarioSeverity = ScenarioSeverity.MODERATE

    # Multipliers applied to baseline
    volume_multiplier: float = 1.0
    spread_multiplier: float = 1.0
    depth_multiplier: float = 1.0
    volatility_multiplier: float = 1.0
    turnover_multiplier: float = 1.0
    participation_multiplier: float = 1.0

    # Scenario metadata
    expected_regime: str = "NORMAL"
    expected_cost_multiplier: float = 1.0
    expected_capacity_multiplier: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "name": self.name,
            "scenario_type": self.scenario_type.value,
            "severity": self.severity.value,
            "volume_multiplier": self.volume_multiplier,
            "spread_multiplier": self.spread_multiplier,
            "depth_multiplier": self.depth_multiplier,
            "volatility_multiplier": self.volatility_multiplier,
            "participation_multiplier": self.participation_multiplier,
            "expected_regime": self.expected_regime,
        }


@dataclass
class ScenarioResult:
    """Result of applying a scenario to a profile."""

    result_id: str = field(default_factory=lambda: f"SR-{uuid.uuid4().hex[:8]}")
    scenario: LiquidityScenario = field(default_factory=LiquidityScenario)
    baseline_profile: LiquidityProfile = field(default_factory=LiquidityProfile)

    # Scenario-applied metrics
    scenario_volume: float = 0.0
    scenario_spread_bps: float = 0.0
    scenario_volatility: float = 0.0
    scenario_depth: float = 0.0
    scenario_turnover: float = 0.0
    scenario_participation_limit: float = 0.0
    scenario_liquidity_score: float = 0.0

    # Capacity impact
    baseline_daily_capacity: float = 0.0
    scenario_daily_capacity: float = 0.0
    capacity_impact_pct: float = 0.0

    # Cost impact
    baseline_cost_bps: float = 0.0
    scenario_cost_bps: float = 0.0
    cost_impact_x: float = 1.0

    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def capacity_decline_pct(self) -> float:
        return max(0.0, -self.capacity_impact_pct * 100)

    @property
    def is_material(self) -> bool:
        """Whether the scenario has material impact (>10% capacity change)."""
        return abs(self.capacity_impact_pct) > 0.10

    def to_dict(self) -> Dict[str, Any]:
        return {
            "result_id": self.result_id,
            "scenario": self.scenario.to_dict(),
            "scenario_liquidity_score": round(self.scenario_liquidity_score, 2),
            "baseline_daily_capacity": self.baseline_daily_capacity,
            "scenario_daily_capacity": self.scenario_daily_capacity,
            "capacity_impact_pct": round(self.capacity_impact_pct, 4),
            "cost_impact_x": round(self.cost_impact_x, 2),
            "is_material": self.is_material,
        }


# ── Pre-defined scenario templates ────────────────────────────────

SCENARIO_TEMPLATES: Dict[str, LiquidityScenario] = {
    "mild_volume_decline": LiquidityScenario(
        name="Mild Volume Decline",
        description="ADV drops 15% — normal market fluctuation",
        scenario_type=ScenarioType.VOLUME_DECLINE,
        severity=ScenarioSeverity.MILD,
        volume_multiplier=0.85,
        spread_multiplier=1.10,
        depth_multiplier=0.90,
        participation_multiplier=0.90,
    ),
    "moderate_volume_decline": LiquidityScenario(
        name="Moderate Volume Decline",
        description="ADV drops 30% — sector rotation",
        scenario_type=ScenarioType.VOLUME_DECLINE,
        severity=ScenarioSeverity.MODERATE,
        volume_multiplier=0.70,
        spread_multiplier=1.50,
        depth_multiplier=0.70,
        participation_multiplier=0.70,
        expected_regime="LOW_LIQUIDITY",
        expected_cost_multiplier=1.5,
    ),
    "severe_volume_decline": LiquidityScenario(
        name="Severe Volume Decline",
        description="ADV drops 50% — broad risk-off event",
        scenario_type=ScenarioType.VOLUME_DECLINE,
        severity=ScenarioSeverity.SEVERE,
        volume_multiplier=0.50,
        spread_multiplier=2.0,
        depth_multiplier=0.50,
        participation_multiplier=0.50,
        expected_regime="STRESSED",
        expected_cost_multiplier=3.0,
    ),
    "spread_widening": LiquidityScenario(
        name="Spread Widening",
        description="Bid-ask spreads triple — liquidity provider withdrawal",
        scenario_type=ScenarioType.SPREAD_WIDENING,
        severity=ScenarioSeverity.MODERATE,
        spread_multiplier=3.0,
        depth_multiplier=0.60,
        participation_multiplier=0.60,
        expected_cost_multiplier=3.0,
    ),
    "vol_spike": LiquidityScenario(
        name="Volatility Spike",
        description="Realized volatility doubles — uncertainty shock",
        scenario_type=ScenarioType.VOLATILITY_SPIKE,
        severity=ScenarioSeverity.MODERATE,
        volatility_multiplier=2.0,
        spread_multiplier=1.30,
        participation_multiplier=0.70,
        expected_regime="LOW_LIQUIDITY",
        expected_cost_multiplier=2.0,
    ),
    "depth_reduction": LiquidityScenario(
        name="Depth Reduction",
        description="Order book depth cut in half — thin markets",
        scenario_type=ScenarioType.DEPTH_REDUCTION,
        severity=ScenarioSeverity.MODERATE,
        depth_multiplier=0.50,
        spread_multiplier=1.50,
        participation_multiplier=0.50,
        expected_cost_multiplier=2.5,
    ),
    "combined_moderate": LiquidityScenario(
        name="Combined Moderate Stress",
        description="ADV -30%, spread x2, vol +50% — typical stress day",
        scenario_type=ScenarioType.COMBINED,
        severity=ScenarioSeverity.MODERATE,
        volume_multiplier=0.70,
        spread_multiplier=2.0,
        volatility_multiplier=1.50,
        depth_multiplier=0.60,
        participation_multiplier=0.50,
        expected_regime="STRESSED",
        expected_cost_multiplier=4.0,
    ),
    "combined_severe": LiquidityScenario(
        name="Combined Severe Stress",
        description="ADV -60%, spread x5, vol x3 — major disruption",
        scenario_type=ScenarioType.COMBINED,
        severity=ScenarioSeverity.SEVERE,
        volume_multiplier=0.40,
        spread_multiplier=5.0,
        volatility_multiplier=3.0,
        depth_multiplier=0.25,
        participation_multiplier=0.20,
        expected_regime="STRESSED",
        expected_cost_multiplier=10.0,
    ),
    "flash_crash": LiquidityScenario(
        name="Flash Crash",
        description="Circuit breaker; liquidity evaporates almost entirely",
        scenario_type=ScenarioType.COMBINED,
        severity=ScenarioSeverity.EXTREME,
        volume_multiplier=0.15,
        spread_multiplier=10.0,
        volatility_multiplier=5.0,
        depth_multiplier=0.05,
        turnover_multiplier=0.10,
        participation_multiplier=0.05,
        expected_regime="CRISIS",
        expected_cost_multiplier=30.0,
        expected_capacity_multiplier=0.01,
    ),
}


class ScenarioRunner:
    """Applies liquidity scenarios and returns results."""

    def __init__(self):
        self._scenarios: Dict[str, LiquidityScenario] = {}

    def register_scenario(self, scenario: LiquidityScenario) -> None:
        self._scenarios[scenario.scenario_id] = scenario

    def load_templates(self) -> None:
        """Load the standard scenario templates."""
        for sid, scenario in SCENARIO_TEMPLATES.items():
            self._scenarios[sid] = scenario

    def run(self, scenario_id: str, profile: LiquidityProfile) -> ScenarioResult:
        """Apply a scenario to a liquidity profile."""
        scenario = self._scenarios.get(scenario_id)
        if scenario is None:
            raise KeyError(f"Scenario not found: {scenario_id}")

        result = ScenarioResult(scenario=scenario, baseline_profile=profile)

        # Apply multipliers
        result.scenario_volume = profile.avg_daily_volume * scenario.volume_multiplier
        result.scenario_spread_bps = profile.spread_bps * scenario.spread_multiplier
        result.scenario_volatility = profile.volatility * scenario.volatility_multiplier
        result.scenario_depth = profile.depth * scenario.depth_multiplier
        result.scenario_turnover = profile.turnover * scenario.turnover_multiplier
        result.scenario_participation_limit = profile.participation_limit * scenario.participation_multiplier

        # Compute liquidity score
        result.scenario_liquidity_score = self._compute_scenario_score(result)

        # Capacity impact
        result.baseline_daily_capacity = profile.avg_daily_volume * profile.participation_limit
        result.scenario_daily_capacity = result.scenario_volume * result.scenario_participation_limit
        if result.baseline_daily_capacity > 0:
            result.capacity_impact_pct = (
                (result.scenario_daily_capacity - result.baseline_daily_capacity)
                / result.baseline_daily_capacity
            )

        # Cost impact
        result.baseline_cost_bps = profile.spread_bps / 2
        result.scenario_cost_bps = result.scenario_spread_bps / 2
        result.cost_impact_x = (
            result.scenario_cost_bps / result.baseline_cost_bps
            if result.baseline_cost_bps > 0 else 1.0
        )

        return result

    def run_all(self, profile: LiquidityProfile) -> Dict[str, ScenarioResult]:
        """Run all registered scenarios against a profile."""
        results: Dict[str, ScenarioResult] = {}
        for sid in self._scenarios:
            try:
                results[sid] = self.run(sid, profile)
            except Exception:
                pass
        return results

    def compare_scenarios(self, profile: LiquidityProfile) -> List[Dict[str, Any]]:
        """Compare and rank scenarios by severity."""
        results = self.run_all(profile)
        ranked = sorted(results.items(), key=lambda x: x[1].capacity_impact_pct)
        return [
            {
                "scenario": sid,
                "name": r.scenario.name,
                "severity": r.scenario.severity.value,
                "capacity_impact_pct": round(r.capacity_impact_pct * 100, 2),
                "cost_impact_x": round(r.cost_impact_x, 2),
                "liquidity_score": round(r.scenario_liquidity_score, 2),
                "is_material": r.is_material,
            }
            for sid, r in ranked
        ]

    # ── Helpers ───────────────────────────────────────────────────

    @staticmethod
    def _compute_scenario_score(result: ScenarioResult) -> float:
        profile = result.baseline_profile
        vol_score = min(30, 30 * result.scenario_volume / max(profile.avg_daily_volume, 1))
        spread_score = (
            min(25, 25 * profile.spread_bps / max(result.scenario_spread_bps, 0.01))
            if result.scenario_spread_bps > 0 else 25
        )
        depth_score = min(20, 20 * result.scenario_depth / max(profile.depth, 1))
        vol_penalty = max(0, 15 * (result.scenario_volatility / max(profile.volatility, 0.01) - 1))
        turnover_score = min(10, 10 * result.scenario_turnover / max(profile.turnover, 0.01))
        return max(0, vol_score + spread_score + depth_score + 15 - vol_penalty + turnover_score)

    def get_scenario(self, scenario_id: str) -> Optional[LiquidityScenario]:
        return self._scenarios.get(scenario_id)

    def scenario_count(self) -> int:
        return len(self._scenarios)

    def list_scenarios(self) -> List[Dict[str, str]]:
        return [
            {"id": sid, "name": s.name, "type": s.scenario_type.value, "severity": s.severity.value}
            for sid, s in self._scenarios.items()
        ]

    def summary(self) -> Dict[str, Any]:
        return {
            "scenarios_available": self.scenario_count(),
            "scenarios": self.list_scenarios(),
        }
