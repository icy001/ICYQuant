"""
Liquidity Profile — Detailed liquidity characteristics per asset.

Core fields: asset, venue, avg_volume, avg_notional, spread, depth,
             volatility, turnover, participation_limit, liquidity_score.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class LiquidityProfile:
    """Detailed liquidity profile for a single trading asset."""

    profile_id: str = field(default_factory=lambda: f"LP-{uuid.uuid4().hex[:8]}")
    asset: str = ""
    venue: str = ""

    # Volume metrics
    avg_daily_volume: float = 0.0         # shares/contracts
    avg_daily_notional: float = 0.0       # dollar value
    median_daily_volume: float = 0.0
    volume_volatility: float = 0.0         # std/mean

    # Spread metrics
    avg_spread_bps: float = 0.0
    median_spread_bps: float = 0.0
    spread_at_volume_pct: Dict[float, float] = field(default_factory=dict)  # participation -> spread

    # Depth
    avg_book_depth: float = 0.0
    depth_decay_rate: float = 0.0

    # Price
    avg_price: float = 0.0
    volatility: float = 0.0

    # Turnover
    turnover_ratio: float = 0.0

    # Capacity limits
    participation_limit: float = 0.10     # max % of daily volume
    max_single_order_pct: float = 0.05

    # Score
    liquidity_score: float = 50.0

    # Category
    liquidity_tier: str = "MID"            # LARGE, MID, SMALL, ILLIQUID

    def to_dict(self) -> Dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "asset": self.asset,
            "venue": self.venue,
            "avg_daily_volume": self.avg_daily_volume,
            "avg_daily_notional": self.avg_daily_notional,
            "avg_spread_bps": self.avg_spread_bps,
            "volatility": self.volatility,
            "liquidity_score": self.liquidity_score,
            "liquidity_tier": self.liquidity_tier,
            "participation_limit": self.participation_limit,
        }

    @property
    def estimated_daily_capacity(self) -> float:
        """Estimated max executable notional per day."""
        return self.avg_daily_notional * self.participation_limit

    @property
    def estimated_instant_capacity(self) -> float:
        """Estimated max executable notional in a single trade."""
        return self.avg_daily_notional * self.max_single_order_pct

    def spread_at_participation(self, participation_pct: float) -> float:
        """Estimate spread at a given participation rate."""
        for pct, spread in sorted(self.spread_at_volume_pct.items()):
            if participation_pct <= pct:
                return spread
        base_spread = self.avg_spread_bps
        return base_spread * (1 + participation_pct * 5)  # Very roughly linear
