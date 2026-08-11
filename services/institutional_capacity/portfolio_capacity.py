"""
Portfolio Capacity — Aggregate capacity across strategies at portfolio level.

Portfolio capacity < Σ Strategy Capacity because strategies compete
for the same assets, liquidity, execution bandwidth, and risk factors.

Provides portfolio-wide capacity assessment: total/available/constrained.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

from .strategy_capacity import StrategyCapacity, StrategyCapacityState


class PortfolioCapacityState(str, Enum):
    UNDER_CAPACITY = "under_capacity"
    OPTIMAL = "optimal"
    PARTIALLY_CONSTRAINED = "partially_constrained"
    FULLY_CONSTRAINED = "fully_constrained"
    OVER_CAPACITY = "over_capacity"


@dataclass
class AssetOverlap:
    """Overlap metrics when multiple strategies target the same asset."""

    asset: str = ""
    strategy_ids: List[str] = field(default_factory=list)
    total_requested: float = 0.0
    available_market_capacity: float = 0.0
    overlap_ratio: float = 0.0
    shortage: float = 0.0

    @property
    def is_oversubscribed(self) -> bool:
        return self.overlap_ratio > 1.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "asset": self.asset,
            "strategy_ids": self.strategy_ids,
            "total_requested": self.total_requested,
            "available_market_capacity": self.available_market_capacity,
            "overlap_ratio": self.overlap_ratio,
            "shortage": self.shortage,
            "is_oversubscribed": self.is_oversubscribed,
        }


@dataclass
class FactorOverlap:
    """Risk factor overlap between strategies."""

    factor: str = ""
    strategy_ids: List[str] = field(default_factory=list)
    total_exposure: float = 0.0
    max_capacity_exposure: float = 0.0
    exposure_ratio: float = 0.0

    @property
    def is_breached(self) -> bool:
        return self.exposure_ratio > 1.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "factor": self.factor,
            "strategy_ids": self.strategy_ids,
            "total_exposure": self.total_exposure,
            "max_capacity_exposure": self.max_capacity_exposure,
            "exposure_ratio": self.exposure_ratio,
            "is_breached": self.is_breached,
        }


@dataclass
class PortfolioCapacity:
    """Aggregate capacity at portfolio level."""

    portfolio_id: str = field(default_factory=lambda: f"PC-{uuid.uuid4().hex[:8]}")
    strategy_capacities: Dict[str, StrategyCapacity] = field(default_factory=dict)

    # Aggregate metrics
    total_optimal: float = 0.0
    total_max_capacity: float = float("inf")
    total_deployed: float = 0.0
    total_utilization: float = 0.0
    effective_capacity: float = 0.0

    # Competition effects
    asset_overlaps: List[AssetOverlap] = field(default_factory=list)
    factor_overlaps: List[FactorOverlap] = field(default_factory=list)
    capacity_discount: float = 1.0  # < 1 if overlap exists

    state: PortfolioCapacityState = PortfolioCapacityState.UNDER_CAPACITY
    constrained_strategies: List[str] = field(default_factory=list)
    binding_assets: List[str] = field(default_factory=list)
    binding_factors: List[str] = field(default_factory=list)

    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def available_capacity(self) -> float:
        """Total deployable capacity after competition adjustment."""
        return max(0.0, self.effective_capacity - self.total_deployed)

    @property
    def remaining_headroom_pct(self) -> float:
        if self.effective_capacity <= 0:
            return 0.0
        return self.available_capacity / self.effective_capacity

    @property
    def strategy_count(self) -> int:
        return len(self.strategy_capacities)

    @property
    def constrained_count(self) -> int:
        return len(self.constrained_strategies)

    @property
    def capacity_efficiency(self) -> float:
        """How efficiently capacity is utilized (1.0 = perfect)."""
        return self.total_utilization if self.total_utilization <= 1.0 else 1.0 / self.total_utilization

    def aggregate(self, strategies: Dict[str, StrategyCapacity]) -> None:
        """Aggregate individual strategy capacities into portfolio view."""
        self.strategy_capacities = strategies
        self.total_optimal = sum(sc.optimal_capital for sc in strategies.values())
        self.total_deployed = sum(sc.current_capital for sc in strategies.values())

        max_caps = [sc.effective_capacity for sc in strategies.values()
                     if sc.effective_capacity != float("inf")]
        self.total_max_capacity = sum(max_caps) if max_caps else float("inf")
        self.effective_capacity = min(self.total_max_capacity / self.capacity_discount,
                                      self.total_max_capacity)

        if self.effective_capacity > 0:
            self.total_utilization = self.total_deployed / self.effective_capacity
        else:
            self.total_utilization = float("inf")

        self.constrained_strategies = [
            sid for sid, sc in strategies.items()
            if sc.state in (StrategyCapacityState.AT_CAPACITY, StrategyCapacityState.OVER_CAPACITY)
        ]

    def evaluate_state(self) -> PortfolioCapacityState:
        constrained_pct = self.constrained_count / max(self.strategy_count, 1)
        if constrained_pct == 0:
            self.state = PortfolioCapacityState.UNDER_CAPACITY
        elif constrained_pct <= 0.3:
            self.state = PortfolioCapacityState.OPTIMAL
        elif constrained_pct <= 0.7:
            self.state = PortfolioCapacityState.PARTIALLY_CONSTRAINED
        else:
            self.state = PortfolioCapacityState.FULLY_CONSTRAINED

        if self.total_utilization > 1.0 and constrained_pct >= 0.5:
            self.state = PortfolioCapacityState.OVER_CAPACITY

        return self.state

    def compute_asset_overlaps(self,
                                strategy_assets: Dict[str, Set[str]],
                                market_capacities: Dict[str, float]) -> List[AssetOverlap]:
        """Detect where strategies compete for the same asset capacity."""
        overlaps: List[AssetOverlap] = []
        asset_to_strategies: Dict[str, Set[str]] = {}

        for sid, assets in strategy_assets.items():
            for asset in assets:
                asset_to_strategies.setdefault(asset, set()).add(sid)

        for asset, sids in asset_to_strategies.items():
            if len(sids) > 1:
                total_req = sum(
                    self.strategy_capacities[sid].current_capital
                    for sid in sids if sid in self.strategy_capacities
                )
                avail = market_capacities.get(asset, float("inf"))
                overlap = AssetOverlap(
                    asset=asset,
                    strategy_ids=sorted(sids),
                    total_requested=total_req,
                    available_market_capacity=avail,
                    overlap_ratio=total_req / avail if avail > 0 else float("inf"),
                    shortage=max(0.0, total_req - avail),
                )
                overlaps.append(overlap)

        self.asset_overlaps = overlaps
        self.binding_assets = [o.asset for o in overlaps if o.is_oversubscribed]

        # Apply capacity discount for oversubscribed assets
        oversubscribed = [o for o in overlaps if o.is_oversubscribed]
        if oversubscribed:
            avg_ratio = sum(o.overlap_ratio for o in oversubscribed) / len(oversubscribed)
            self.capacity_discount = max(0.5, 1.0 / avg_ratio)

        return overlaps

    def compute_factor_overlaps(self,
                                 strategy_factors: Dict[str, Dict[str, float]],
                                 factor_limits: Dict[str, float]) -> List[FactorOverlap]:
        """Detect risk factor concentration across strategies."""
        overlaps: List[FactorOverlap] = []
        factor_aggregates: Dict[str, Tuple[float, Set[str]]] = {}

        for sid, factors in strategy_factors.items():
            for factor, exposure in factors.items():
                if factor not in factor_aggregates:
                    factor_aggregates[factor] = (0.0, set())
                total, sids = factor_aggregates[factor]
                factor_aggregates[factor] = (total + abs(exposure), sids | {sid})

        for factor, (total_exp, sids) in factor_aggregates.items():
            limit = factor_limits.get(factor, float("inf"))
            if len(sids) > 1 or total_exp > limit * 0.5:
                overlaps.append(FactorOverlap(
                    factor=factor,
                    strategy_ids=sorted(sids),
                    total_exposure=total_exp,
                    max_capacity_exposure=limit,
                    exposure_ratio=total_exp / limit if limit > 0 else float("inf"),
                ))

        self.factor_overlaps = overlaps
        self.binding_factors = [o.factor for o in overlaps if o.is_breached]
        return overlaps

    def to_dict(self) -> Dict[str, Any]:
        return {
            "portfolio_id": self.portfolio_id,
            "strategy_count": self.strategy_count,
            "constrained_count": self.constrained_count,
            "total_optimal": self.total_optimal,
            "total_max_capacity": self.total_max_capacity,
            "total_deployed": self.total_deployed,
            "total_utilization": self.total_utilization,
            "effective_capacity": self.effective_capacity,
            "available_capacity": self.available_capacity,
            "capacity_discount": self.capacity_discount,
            "state": self.state.value,
            "asset_overlaps": [o.to_dict() for o in self.asset_overlaps],
            "factor_overlaps": [o.to_dict() for o in self.factor_overlaps],
            "constrained_strategies": self.constrained_strategies,
            "binding_assets": self.binding_assets,
            "binding_factors": self.binding_factors,
            "timestamp": self.timestamp.isoformat(),
        }

    def summary(self) -> Dict[str, Any]:
        return {
            "strategies": self.strategy_count,
            "constrained": self.constrained_count,
            "utilization_pct": round(self.total_utilization * 100, 2),
            "available_headroom": self.available_capacity,
            "headroom_pct": round(self.remaining_headroom_pct * 100, 2),
            "asset_overlaps": len([o for o in self.asset_overlaps if o.is_oversubscribed]),
            "factor_overlaps": len([o for o in self.factor_overlaps if o.is_breached]),
            "capacity_discount": round(self.capacity_discount, 4),
            "state": self.state.value,
        }
