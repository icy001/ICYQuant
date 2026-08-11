"""
Capacity Intelligence — Central engine for institutional capacity management.

Determines real-world executable capacity by integrating:
    Strategy Capacity → Market Liquidity → Execution Capacity → Market Impact

Answers: "How much capital can the market safely absorb right now?"
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class CapacityState(str, Enum):
    """Capacity lifecycle state."""
    AVAILABLE = "available"
    ALLOCATABLE = "allocatable"
    CAPACITY_CHECK = "capacity_check"
    LIQUIDITY_CHECK = "liquidity_check"
    IMPACT_CHECK = "impact_check"
    EXECUTABLE = "executable"
    DEGRADED = "degraded"
    RESIZED = "resized"
    FROZEN = "frozen"
    REJECTED = "rejected"


@dataclass
class CapacitySnapshot:
    """Point-in-time capacity assessment for a capital allocation."""

    snapshot_id: str = field(default_factory=lambda: f"CS-{uuid.uuid4().hex[:8]}")
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    strategy_id: str = ""
    asset: str = ""

    # Requested vs actual
    requested_capital: float = 0.0
    executable_capital: float = 0.0
    utilization: float = 0.0

    # Capacity limits
    strategy_capacity_limit: float = float("inf")
    asset_capacity_limit: float = float("inf")
    market_capacity_limit: float = float("inf")
    execution_capacity_limit: float = float("inf")

    # Liquidity
    liquidity_score: float = 0.0
    liquidity_regime: str = "NORMAL"
    participation_rate: float = 0.0

    # Impact
    expected_impact_bps: float = 0.0
    temporary_impact_bps: float = 0.0
    permanent_impact_bps: float = 0.0
    expected_slippage_bps: float = 0.0

    # Decision
    state: CapacityState = CapacityState.AVAILABLE
    binding_constraint: str = ""
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "strategy_id": self.strategy_id,
            "asset": self.asset,
            "requested_capital": self.requested_capital,
            "executable_capital": self.executable_capital,
            "liquidity_score": self.liquidity_score,
            "expected_impact_bps": self.expected_impact_bps,
            "state": self.state.value,
            "binding_constraint": self.binding_constraint,
        }

    @property
    def resize_ratio(self) -> float:
        return self.executable_capital / max(self.requested_capital, 1.0)

    @property
    def is_constrained(self) -> bool:
        return self.executable_capital < self.requested_capital


class CapacityIntelligenceContext:
    """Context for capacity intelligence evaluation pipeline."""

    def __init__(self):
        self.strategy_capacities: Dict[str, float] = {}
        self.asset_capacities: Dict[str, float] = {}
        self.liquidity_scores: Dict[str, float] = {}
        self.liquidity_regime: str = "NORMAL"
        self.max_participation_rate: float = 0.10
        self.impact_budget_bps: float = 15.0
        self.min_liquidity_score: float = 30.0


class CapacityIntelligence:
    """Central capacity engine evaluating executable capacity.

    Pipeline: Strategy Capacity → Market Liquidity → Impact → Execution Capacity
    """

    def __init__(self):
        self._snapshots: List[CapacitySnapshot] = []
        self._context = CapacityIntelligenceContext()

    @property
    def context(self) -> CapacityIntelligenceContext:
        return self._context

    def assess(
        self,
        strategy_id: str,
        asset: str,
        requested_capital: float,
        avg_daily_volume: float = 0.0,
        volatility: float = 0.0,
        spread_bps: float = 0.0,
    ) -> CapacitySnapshot:
        """Full capacity assessment pipeline."""
        snapshot = CapacitySnapshot(
            strategy_id=strategy_id,
            asset=asset,
            requested_capital=requested_capital,
        )

        ctx = self._context

        # Step 1: Strategy capacity limit
        snapshot.strategy_capacity_limit = ctx.strategy_capacities.get(strategy_id, float("inf"))
        snapshot.asset_capacity_limit = ctx.asset_capacities.get(asset, float("inf"))

        # Participation check
        if avg_daily_volume > 0:
            snapshot.participation_rate = requested_capital / avg_daily_volume
            if snapshot.participation_rate > ctx.max_participation_rate:
                snapshot.execution_capacity_limit = avg_daily_volume * ctx.max_participation_rate

        # Liquidity
        snapshot.liquidity_score = ctx.liquidity_scores.get(asset, 50.0)
        snapshot.liquidity_regime = ctx.liquidity_regime

        # Impact estimation (simplified square-root model)
        if avg_daily_volume > 0:
            participation = requested_capital / avg_daily_volume
            volatility_pct = volatility if volatility > 0 else 0.02
            snapshot.expected_impact_bps = volatility_pct * (participation ** 0.5) * 10000
            snapshot.temporary_impact_bps = snapshot.expected_impact_bps * 0.6
            snapshot.permanent_impact_bps = snapshot.expected_impact_bps * 0.4
            snapshot.expected_slippage_bps = spread_bps * 0.5 + snapshot.temporary_impact_bps

        # Effective capacity = MIN of all limits
        limits = [
            snapshot.strategy_capacity_limit,
            snapshot.asset_capacity_limit,
            snapshot.market_capacity_limit,
            snapshot.execution_capacity_limit if snapshot.execution_capacity_limit > 0 else float("inf"),
        ]
        effective_limit = min(limits)

        if requested_capital > effective_limit:
            snapshot.executable_capital = effective_limit
            snapshot.binding_constraint = "strategy_capacity" if effective_limit == snapshot.strategy_capacity_limit else (
                "asset_capacity" if effective_limit == snapshot.asset_capacity_limit else "participation_rate"
            )
            snapshot.state = CapacityState.RESIZED
        else:
            snapshot.executable_capital = requested_capital

        # Impact budget check
        if snapshot.expected_impact_bps > ctx.impact_budget_bps:
            snapshot.state = CapacityState.RESIZED
            snapshot.warnings.append(f"Impact {snapshot.expected_impact_bps:.1f} bps exceeds budget {ctx.impact_budget_bps} bps")

        # Liquidity check
        if snapshot.liquidity_score < ctx.min_liquidity_score:
            if snapshot.state not in (CapacityState.RESIZED, CapacityState.REJECTED):
                snapshot.state = CapacityState.DEGRADED
            snapshot.warnings.append(f"Low liquidity score: {snapshot.liquidity_score:.0f}")

        # Final state transition
        if snapshot.state == CapacityState.AVAILABLE and snapshot.utilization < 1.0:
            snapshot.state = CapacityState.EXECUTABLE

        snapshot.utilization = snapshot.executable_capital / max(effective_limit, 1.0)
        self._snapshots.append(snapshot)
        return snapshot

    def batch_assess(
        self,
        requests: List[Tuple[str, str, float, float, float, float]],
    ) -> List[CapacitySnapshot]:
        """Assess multiple capacity requests."""
        return [
            self.assess(sid, asset, cap, adv, vol, spread)
            for sid, asset, cap, adv, vol, spread in requests
        ]

    def history(self) -> List[CapacitySnapshot]:
        return list(self._snapshots)

    def summary(self) -> Dict[str, Any]:
        if not self._snapshots:
            return {"assessments": 0}
        resized = sum(1 for s in self._snapshots if s.state == CapacityState.RESIZED)
        return {
            "total_assessments": len(self._snapshots),
            "executable": sum(1 for s in self._snapshots if s.state == CapacityState.EXECUTABLE),
            "resized": resized,
            "degraded": sum(1 for s in self._snapshots if s.state == CapacityState.DEGRADED),
            "avg_impact_bps": sum(s.expected_impact_bps for s in self._snapshots) / len(self._snapshots),
        }
