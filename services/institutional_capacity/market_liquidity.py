"""
Market Liquidity — Real-time market liquidity assessment and snapshot.

Aggregates liquidity data per asset and produces actionable snapshots.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class LiquidityLevel(str, Enum):
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"
    STRESSED = "stressed"
    CRISIS = "crisis"


@dataclass
class LiquiditySnapshot:
    """Point-in-time liquidity snapshot for an asset."""

    snapshot_id: str = field(default_factory=lambda: f"LS-{uuid.uuid4().hex[:8]}")
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    asset: str = ""

    # Volume
    avg_daily_volume: float = 0.0
    current_volume: float = 0.0
    volume_percentile: float = 0.0      # vs historical

    # Spread
    bid_ask_spread_bps: float = 0.0
    effective_spread_bps: float = 0.0

    # Depth
    book_depth_bid: float = 0.0
    book_depth_ask: float = 0.0

    # Derived
    liquidity_score: float = 50.0
    liquidity_level: LiquidityLevel = LiquidityLevel.NORMAL
    max_participation_rate: float = 0.10

    # Capacity
    daily_capacity: float = 0.0         # estimated executable per day
    instantaneous_capacity: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "asset": self.asset,
            "avg_daily_volume": self.avg_daily_volume,
            "spread_bps": self.bid_ask_spread_bps,
            "liquidity_score": self.liquidity_score,
            "level": self.liquidity_level.value,
            "daily_capacity": self.daily_capacity,
        }


class MarketLiquidity:
    """Aggregated market liquidity intelligence."""

    def __init__(self):
        self._snapshots: Dict[str, LiquiditySnapshot] = {}
        self._regime: str = "NORMAL"

    def update(self, snapshot: LiquiditySnapshot) -> None:
        self._snapshots[snapshot.asset] = snapshot

    def get(self, asset: str) -> Optional[LiquiditySnapshot]:
        return self._snapshots.get(asset)

    def daily_capacity(self, asset: str) -> float:
        snap = self._snapshots.get(asset)
        if not snap:
            return 0.0
        return snap.daily_capacity

    def can_trade(self, asset: str, amount: float, max_participation: float = 0.10) -> bool:
        snap = self._snapshots.get(asset)
        if not snap or snap.avg_daily_volume <= 0:
            return False
        return amount <= snap.avg_daily_volume * max_participation

    def lowest_liquidity_assets(self, n: int = 5) -> List[str]:
        sorted_assets = sorted(self._snapshots.keys(), key=lambda a: self._snapshots[a].liquidity_score)
        return sorted_assets[:n]

    def summary(self) -> Dict[str, Any]:
        if not self._snapshots:
            return {"assets": 0}
        scores = [s.liquidity_score for s in self._snapshots.values()]
        return {
            "assets_tracked": len(self._snapshots),
            "avg_liquidity_score": sum(scores) / len(scores),
            "min_liquidity_score": min(scores),
            "stressed_assets": sum(1 for s in self._snapshots.values() if s.liquidity_level in (LiquidityLevel.LOW, LiquidityLevel.STRESSED, LiquidityLevel.CRISIS)),
        }
