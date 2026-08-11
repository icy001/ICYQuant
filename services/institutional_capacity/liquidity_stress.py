"""
Liquidity Stress — Stress tests liquidity conditions under adverse scenarios.

Simulates extreme market conditions:
- Volume collapse (flash crash, circuit breaker)
- Spread explosion (liquidity crisis)
- Volatility spike (VIX shock)
- Combined multi-factor stress
"""

from __future__ import annotations

import math
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from .liquidity_regime import LiquidityRegime, LiquidityRegimeDetector
from .liquidity_profile import LiquidityProfile


class StressType(str, Enum):
    VOLUME_COLLAPSE = "volume_collapse"
    SPREAD_EXPLOSION = "spread_explosion"
    VOLATILITY_SPIKE = "volatility_spike"
    COMBINED = "combined"
    TAIL_EVENT = "tail_event"
    CIRCUIT_BREAKER = "circuit_breaker"
    CUSTOM = "custom"


class StressSeverity(str, Enum):
    MODERATE = "moderate"
    SEVERE = "severe"
    EXTREME = "extreme"


@dataclass
class StressScenario:
    """Definition of a liquidity stress scenario."""

    scenario_id: str = field(default_factory=lambda: f"LSS-{uuid.uuid4().hex[:8]}")
    name: str = ""
    description: str = ""
    stress_type: StressType = StressType.CUSTOM
    severity: StressSeverity = StressSeverity.MODERATE

    # Shock multipliers (relative to baseline)
    volume_multiplier: float = 1.0      # < 1 = volume drop
    spread_multiplier: float = 1.0      # > 1 = spread widening
    volatility_multiplier: float = 1.0   # > 1 = vol spike
    depth_multiplier: float = 1.0        # < 1 = depth reduction
    turnover_multiplier: float = 1.0     # < 1 = turnover drop
    participation_cap_multiplier: float = 1.0  # < 1 = lower participation limit

    # Stress impact estimates
    expected_regime_shift: Optional[str] = None
    expected_cost_multiplier: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "name": self.name,
            "stress_type": self.stress_type.value,
            "severity": self.severity.value,
            "volume_multiplier": self.volume_multiplier,
            "spread_multiplier": self.spread_multiplier,
            "volatility_multiplier": self.volatility_multiplier,
            "depth_multiplier": self.depth_multiplier,
            "turnover_multiplier": self.turnover_multiplier,
            "participation_cap_multiplier": self.participation_cap_multiplier,
            "expected_regime_shift": self.expected_regime_shift,
            "expected_cost_multiplier": self.expected_cost_multiplier,
        }


@dataclass
class StressResult:
    """Result of applying a stress scenario to a liquidity profile."""

    result_id: str = field(default_factory=lambda: f"LSR-{uuid.uuid4().hex[:8]}")
    scenario: StressScenario = field(default_factory=StressScenario)
    profile: LiquidityProfile = field(default_factory=LiquidityProfile)
    is_survivable: bool = True

    # Stressed metrics
    stressed_volume: float = 0.0
    stressed_spread_bps: float = 0.0
    stressed_volatility: float = 0.0
    stressed_depth: float = 0.0
    stressed_turnover: float = 0.0
    stressed_participation_cap: float = 0.0
    stressed_liquidity_score: float = 0.0
    stressed_regime: Optional[str] = None

    # Impact
    estimated_transaction_cost_bps: float = 0.0
    estimated_impact_bps: float = 0.0
    estimated_liquidation_days: float = 0.0
    estimated_liquidation_cost_bps: float = 0.0
    capacity_remaining_pct: float = 100.0
    max_safe_order: float = 0.0

    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "result_id": self.result_id,
            "scenario": self.scenario.to_dict(),
            "is_survivable": self.is_survivable,
            "stressed_volume": self.stressed_volume,
            "stressed_spread_bps": self.stressed_spread_bps,
            "stressed_volatility": self.stressed_volatility,
            "stressed_depth": self.stressed_depth,
            "stressed_liquidity_score": self.stressed_liquidity_score,
            "stressed_regime": self.stressed_regime,
            "estimated_transaction_cost_bps": self.estimated_transaction_cost_bps,
            "estimated_impact_bps": self.estimated_impact_bps,
            "estimated_liquidation_days": self.estimated_liquidation_days,
            "estimated_liquidation_cost_bps": self.estimated_liquidation_cost_bps,
            "capacity_remaining_pct": self.capacity_remaining_pct,
            "max_safe_order": self.max_safe_order,
        }


# ── Pre-defined stress scenarios ──────────────────────────────────

STANDARD_STRESS_SCENARIOS: Dict[str, StressScenario] = {
    "moderate_vol_drop": StressScenario(
        name="Moderate Volume Drop",
        description="30% volume decline (sector rotation)",
        stress_type=StressType.VOLUME_COLLAPSE,
        severity=StressSeverity.MODERATE,
        volume_multiplier=0.70,
        spread_multiplier=1.5,
        depth_multiplier=0.70,
    ),
    "severe_vol_drop": StressScenario(
        name="Severe Volume Drop",
        description="50% volume decline (broad risk-off)",
        stress_type=StressType.VOLUME_COLLAPSE,
        severity=StressSeverity.SEVERE,
        volume_multiplier=0.50,
        spread_multiplier=2.0,
        depth_multiplier=0.50,
        participation_cap_multiplier=0.70,
    ),
    "flash_crash": StressScenario(
        name="Flash Crash",
        description="Circuit breaker triggered, liquidity evaporates",
        stress_type=StressType.CIRCUIT_BREAKER,
        severity=StressSeverity.EXTREME,
        volume_multiplier=0.20,
        spread_multiplier=5.0,
        volatility_multiplier=5.0,
        depth_multiplier=0.10,
        turnover_multiplier=0.10,
        participation_cap_multiplier=0.10,
        expected_regime_shift="CRISIS",
    ),
    "spread_explosion": StressScenario(
        name="Spread Explosion",
        description="Bid-ask spreads widen 10x (liquidity crisis)",
        stress_type=StressType.SPREAD_EXPLOSION,
        severity=StressSeverity.SEVERE,
        spread_multiplier=10.0,
        depth_multiplier=0.30,
        expected_cost_multiplier=8.0,
    ),
    "vol_spike": StressScenario(
        name="Volatility Spike",
        description="Annualized vol doubles (VIX shock)",
        stress_type=StressType.VOLATILITY_SPIKE,
        severity=StressSeverity.SEVERE,
        volatility_multiplier=2.5,
        spread_multiplier=2.0,
        expected_regime_shift="STRESSED",
    ),
    "combined_crisis": StressScenario(
        name="Combined Crisis",
        description="Multi-factor: vol -60%, spread 5x, volatility 3x",
        stress_type=StressType.COMBINED,
        severity=StressSeverity.EXTREME,
        volume_multiplier=0.40,
        spread_multiplier=5.0,
        volatility_multiplier=3.0,
        depth_multiplier=0.20,
        turnover_multiplier=0.25,
        expected_regime_shift="CRISIS",
        expected_cost_multiplier=15.0,
    ),
    "2008_style": StressScenario(
        name="2008-Style Crisis",
        description="GFC-level stress: 80% volume decline, 20x spreads",
        stress_type=StressType.TAIL_EVENT,
        severity=StressSeverity.EXTREME,
        volume_multiplier=0.20,
        spread_multiplier=20.0,
        volatility_multiplier=5.0,
        depth_multiplier=0.05,
        turnover_multiplier=0.05,
        participation_cap_multiplier=0.05,
        expected_regime_shift="CRISIS",
        expected_cost_multiplier=50.0,
    ),
}


class LiquidityStressTester:
    """Applies stress scenarios to liquidity profiles and evaluates survivability."""

    def __init__(self):
        self._scenarios: Dict[str, StressScenario] = {}
        self._results: List[StressResult] = []
        self._regime_detector = LiquidityRegimeDetector()

    def register_scenario(self, scenario: StressScenario) -> None:
        self._scenarios[scenario.scenario_id] = scenario

    def load_standard_scenarios(self) -> None:
        for sid, scenario in STANDARD_STRESS_SCENARIOS.items():
            self._scenarios[sid] = scenario

    def apply_stress(self, scenario_id: str, profile: LiquidityProfile) -> StressResult:
        """Apply a stress scenario to a liquidity profile."""
        scenario = self._scenarios.get(scenario_id)
        if scenario is None:
            scenario = StressScenario(name="Unknown", description="Unknown scenario")

        result = StressResult(scenario=scenario, profile=profile)

        # Apply shocks
        result.stressed_volume = profile.avg_daily_volume * scenario.volume_multiplier
        result.stressed_spread_bps = profile.spread_bps * scenario.spread_multiplier
        result.stressed_volatility = profile.volatility * scenario.volatility_multiplier
        result.stressed_depth = profile.depth * scenario.depth_multiplier
        result.stressed_turnover = profile.turnover * scenario.turnover_multiplier
        result.stressed_participation_cap = (
            profile.participation_limit * scenario.participation_cap_multiplier
        )

        # Compute stressed liquidity score
        result.stressed_liquidity_score = self._compute_stressed_score(result)

        # Detect regime
        result.stressed_regime = scenario.expected_regime_shift or self._detect_stressed_regime(result)

        # Estimate transaction costs under stress
        result.estimated_transaction_cost_bps = self._estimate_cost(result)
        result.estimated_impact_bps = self._estimate_impact(result)
        result.estimated_liquidation_days = self._estimate_liquidation_days(result)
        result.estimated_liquidation_cost_bps = self._estimate_liquidation_cost(result)

        # Compute remaining safe capacity
        result.max_safe_order = result.stressed_volume * result.stressed_participation_cap
        result.capacity_remaining_pct = max(0.0, 100.0 * (
            result.stressed_volume / max(profile.avg_daily_volume, 1)
        ))

        # Survivability: capacity > 5% and score > 10
        result.is_survivable = (
            result.capacity_remaining_pct >= 5.0
            and result.stressed_liquidity_score >= 10.0
        )

        self._results.append(result)
        return result

    def run_battery(self, profile: LiquidityProfile) -> Dict[str, StressResult]:
        """Run all registered stress scenarios against a profile."""
        results: Dict[str, StressResult] = {}
        for sid in self._scenarios:
            results[sid] = self.apply_stress(sid, profile)
        return results

    def worst_case(self, profile: LiquidityProfile) -> Tuple[str, StressResult]:
        """Find the worst-case scenario for a profile."""
        battery = self.run_battery(profile)
        if not battery:
            raise ValueError("No scenarios registered")
        return min(battery.items(), key=lambda x: x[1].stressed_liquidity_score)

    def survivable_scenarios(self, results: Dict[str, StressResult]) -> List[str]:
        return [sid for sid, r in results.items() if r.is_survivable]

    def fatal_scenarios(self, results: Dict[str, StressResult]) -> List[str]:
        return [sid for sid, r in results.items() if not r.is_survivable]

    # ── Internal Estimation ───────────────────────────────────────

    def _compute_stressed_score(self, result: StressResult) -> float:
        """Approximate liquidity score under stress."""
        volume_score = max(0, min(30, 30 * result.stressed_volume / max(result.profile.avg_daily_volume, 1)))
        if result.stressed_spread_bps > 0:
            spread_score = max(0, min(25, 25 * result.profile.spread_bps / result.stressed_spread_bps))
        else:
            spread_score = 25
        depth_score = max(0, min(20, 20 * result.stressed_depth / max(result.profile.depth, 1)))
        volatility_penalty = max(0, min(15, 15 * (result.stressed_volatility / max(result.profile.volatility, 0.01) - 1)))
        turnover_score = max(0, min(10, 10 * result.stressed_turnover / max(result.profile.turnover, 0.01)))
        return volume_score + spread_score + depth_score + 15 - volatility_penalty + turnover_score

    @staticmethod
    def _detect_stressed_regime(result: StressResult) -> str:
        score = result.stressed_liquidity_score
        if score >= 70:
            return "NORMAL"
        elif score >= 50:
            return "LOW_LIQUIDITY"
        elif score >= 30:
            return "STRESSED"
        else:
            return "CRISIS"

    def _estimate_cost(self, result: StressResult) -> float:
        """Estimate transaction cost under stress."""
        spread_cost = result.stressed_spread_bps / 2  # half spread
        vol_impact = result.stressed_volatility * 0.1
        liquidity_penalty = max(0, (50 - result.stressed_liquidity_score) * 0.5)
        return spread_cost + vol_impact + liquidity_penalty

    def _estimate_impact(self, result: StressResult) -> float:
        """Estimate market impact under stress."""
        if result.stressed_volume <= 0:
            return 0.0
        participation = result.profile.avg_daily_volume * 0.01 / result.stressed_volume
        return result.stressed_volatility * 0.1 * math.sqrt(participation) * 10000

    def _estimate_liquidation_days(self, result: StressResult) -> float:
        """Estimate days to liquidate position under stress."""
        if result.stressed_volume <= 0:
            return float("inf")
        position = result.profile.avg_daily_volume * 0.1  # assume 10% position
        daily_capacity = result.stressed_volume * result.stressed_participation_cap
        if daily_capacity <= 0:
            return float("inf")
        return position / daily_capacity

    def _estimate_liquidation_cost(self, result: StressResult) -> float:
        """Total cost to liquidate under stress."""
        cost_per_day = self._estimate_cost(result)
        days = self._estimate_liquidation_days(result)
        if days == float("inf"):
            return float("inf")
        return cost_per_day * days * 1.5  # urgency premium

    # ── Reporting ─────────────────────────────────────────────────

    def get_scenario(self, scenario_id: str) -> Optional[StressScenario]:
        return self._scenarios.get(scenario_id)

    def scenario_names(self) -> List[str]:
        return [(sid, s.name) for sid, s in self._scenarios.items()]

    def recent_results(self, limit: int = 50) -> List[StressResult]:
        return self._results[-limit:]

    def summary(self) -> Dict[str, Any]:
        return {
            "scenarios_available": len(self._scenarios),
            "scenarios_run": len(self._results),
            "scenario_names": dict(self.scenario_names()),
            "standard_loaded": any(
                sid in self._scenarios for sid in STANDARD_STRESS_SCENARIOS
            ),
        }
