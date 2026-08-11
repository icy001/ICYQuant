"""
Liquidity Stress — Tests capital pool survival under liquidity crises.

Simulates:
    Market-wide liquidity evaporation
    Asset-specific liquidity freezes
    Multi-strategy liquidity competition
    Forced liquidation costs under stress
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class LiquidityStressType(str, Enum):
    MARKET_WIDE = "market_wide"
    ASSET_SPECIFIC = "asset_specific"
    STRATEGY_COMPETITION = "strategy_competition"
    FORCED_LIQUIDATION = "forced_liquidation"


class LiquidityRegime(str, Enum):
    NORMAL = "normal"
    STRESSED = "stressed"
    FROZEN = "frozen"
    CRISIS = "crisis"


@dataclass
class LiquidityCluster:
    """A group of strategies competing for the same liquidity pool."""

    cluster_id: str = field(default_factory=lambda: f"LC-{uuid.uuid4().hex[:8]}")
    name: str = ""
    strategy_ids: List[str] = field(default_factory=list)
    asset_universe: List[str] = field(default_factory=list)
    total_capital: float = 0.0
    avg_daily_volume: float = 0.0
    participation_rate: float = 0.0

    @property
    def liquidity_ratio(self) -> float:
        """Capital / average daily volume."""
        return self.total_capital / max(self.avg_daily_volume, 1.0)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cluster_id": self.cluster_id,
            "name": self.name,
            "strategy_count": len(self.strategy_ids),
            "total_capital": self.total_capital,
            "avg_daily_volume": self.avg_daily_volume,
            "participation_rate": self.participation_rate,
            "liquidity_ratio": self.liquidity_ratio,
        }


@dataclass
class LiquidityStressScenario:
    """A liquidity stress scenario definition."""

    scenario_id: str = field(default_factory=lambda: f"LS-{uuid.uuid4().hex[:8]}")
    name: str = ""
    stress_type: LiquidityStressType = LiquidityStressType.MARKET_WIDE
    description: str = ""

    # Liquidity shocks
    volume_reduction_pct: float = 0.0      # e.g. 0.50 = 50% volume decline
    spread_widening_factor: float = 1.0     # e.g. 3.0 = 3x normal spread
    market_impact_factor: float = 1.0       # e.g. 2.0 = 2x normal impact
    liquidation_discount: float = 0.0       # e.g. 0.10 = 10% discount for forced sale

    # Duration
    stress_horizon_days: int = 5

    # Cluster settings
    target_clusters: List[str] = field(default_factory=list)
    max_participation_rate: float = 0.10

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "name": self.name,
            "type": self.stress_type.value,
            "volume_reduction_pct": self.volume_reduction_pct,
            "spread_widening_factor": self.spread_widening_factor,
            "market_impact_factor": self.market_impact_factor,
        }


@dataclass
class LiquidityStressResult:
    """Result of a liquidity stress test."""

    scenario_id: str = ""
    scenario_name: str = ""

    # Pre-stress
    normal_liquidity_ratio: float = 0.0
    normal_days_to_liquidate: float = 0.0

    # Under stress
    stressed_volume: float = 0.0
    stressed_spread_cost: float = 0.0
    stressed_market_impact: float = 0.0
    stressed_liquidation_cost: float = 0.0
    stressed_liquidation_cost_pct: float = 0.0
    stressed_days_to_liquidate: float = 0.0

    # Cluster impact
    cluster_impacts: Dict[str, Dict[str, float]] = field(default_factory=dict)

    # Survival
    survived: bool = True
    capital_at_risk: float = 0.0
    recommended_participation_cap: float = 0.0

    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "scenario_name": self.scenario_name,
            "stressed_spread_cost": self.stressed_spread_cost,
            "stressed_market_impact": self.stressed_market_impact,
            "stressed_liquidation_cost_pct": self.stressed_liquidation_cost_pct,
            "stressed_days_to_liquidate": self.stressed_days_to_liquidate,
            "survived": self.survived,
            "capital_at_risk": self.capital_at_risk,
            "warnings": self.warnings,
        }


class LiquidityStressTester:
    """Tests portfolio survival under liquidity stress conditions."""

    def __init__(self):
        self._clusters: Dict[str, LiquidityCluster] = {}
        self._scenarios: List[LiquidityStressScenario] = []
        self._results: List[LiquidityStressResult] = []

    def register_cluster(self, cluster: LiquidityCluster) -> None:
        self._clusters[cluster.cluster_id] = cluster

    def register_scenario(self, scenario: LiquidityStressScenario) -> None:
        self._scenarios.append(scenario)

    @classmethod
    def standard_scenarios(cls) -> List[LiquidityStressScenario]:
        return [
            LiquidityStressScenario(
                name="Volume Decline -30%",
                stress_type=LiquidityStressType.MARKET_WIDE,
                description="Moderate market-wide volume decline",
                volume_reduction_pct=0.30,
                spread_widening_factor=1.5,
                market_impact_factor=1.3,
            ),
            LiquidityStressScenario(
                name="Volume Decline -60%",
                stress_type=LiquidityStressType.MARKET_WIDE,
                description="Severe liquidity evaporation",
                volume_reduction_pct=0.60,
                spread_widening_factor=3.0,
                market_impact_factor=2.5,
                liquidation_discount=0.05,
            ),
            LiquidityStressScenario(
                name="Liquidity Freeze",
                stress_type=LiquidityStressType.FROZEN,
                description="Near-complete liquidity freeze",
                volume_reduction_pct=0.85,
                spread_widening_factor=5.0,
                market_impact_factor=5.0,
                liquidation_discount=0.15,
                stress_horizon_days=10,
            ),
            LiquidityStressScenario(
                name="Strategy Competition Spike",
                stress_type=LiquidityStressType.STRATEGY_COMPETITION,
                description="Multiple strategies rush for same liquidity",
                volume_reduction_pct=0.20,
                spread_widening_factor=2.0,
                market_impact_factor=2.0,
                max_participation_rate=0.05,
            ),
        ]

    def run(self, scenario: LiquidityStressScenario,
            total_capital: float = 100.0,
            avg_daily_volume: float = 50.0) -> LiquidityStressResult:
        """Run a single liquidity stress scenario."""
        result = LiquidityStressResult(
            scenario_id=scenario.scenario_id,
            scenario_name=scenario.name,
        )

        # Normal conditions
        normal_volume = avg_daily_volume
        result.normal_liquidity_ratio = total_capital / max(normal_volume, 1.0)
        result.normal_days_to_liquidate = total_capital / max(normal_volume * 0.10, 1.0)

        # Stressed conditions
        stressed_volume = normal_volume * (1.0 - scenario.volume_reduction_pct)
        result.stressed_volume = stressed_volume

        # Costs under stress
        normal_spread_cost = total_capital * 0.0010  # 10 bps normal
        result.stressed_spread_cost = normal_spread_cost * scenario.spread_widening_factor

        normal_impact = total_capital * 0.0005  # 5 bps normal
        result.stressed_market_impact = normal_impact * scenario.market_impact_factor

        # Forced liquidation cost
        result.stressed_liquidation_cost = total_capital * scenario.liquidation_discount

        total_stress_cost = result.stressed_spread_cost + result.stressed_market_impact + result.stressed_liquidation_cost
        result.stressed_liquidation_cost_pct = total_stress_cost / max(total_capital, 1.0)

        # Days to liquidate under stress
        if stressed_volume > 0:
            result.stressed_days_to_liquidate = total_capital / max(stressed_volume * 0.10, 1.0)
        else:
            result.stressed_days_to_liquidate = float("inf")

        result.capital_at_risk = total_stress_cost
        result.recommended_participation_cap = scenario.max_participation_rate

        # Survival assessment
        if result.stressed_liquidation_cost_pct > 0.10:
            result.survived = False
            result.warnings.append(f"Liquidation cost {result.stressed_liquidation_cost_pct:.2%} exceeds 10% capital")
        if result.stressed_days_to_liquidate > 20:
            result.warnings.append(f"Liquidation horizon {result.stressed_days_to_liquidate:.0f} days — illiquid")
        if result.stressed_days_to_liquidate > 100:
            result.warnings.append("CRITICAL: Portfolio is illiquid under stress")

        self._results.append(result)
        return result

    def run_all(self, total_capital: float = 100.0, avg_daily_volume: float = 50.0) -> List[LiquidityStressResult]:
        return [self.run(s, total_capital, avg_daily_volume) for s in self._scenarios]

    def summary(self) -> Dict[str, Any]:
        if not self._results:
            return {"error": "No tests run"}
        survived = sum(1 for r in self._results if r.survived)
        return {
            "total_tests": len(self._results),
            "survived": survived,
            "failed": len(self._results) - survived,
            "worst_liquidation_cost_pct": max(r.stressed_liquidation_cost_pct for r in self._results),
            "longest_liquidation_days": max(r.stressed_days_to_liquidate for r in self._results if r.stressed_days_to_liquidate != float("inf")),
            "details": [r.to_dict() for r in self._results],
        }
