"""
Liquidity Estimator — Estimates liquidity characteristics for assets.

Produces LiquidityProfiles from market data (volume, spread, depth, volatility).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .liquidity_profile import LiquidityProfile


@dataclass
class LiquidityEstimate:
    """Raw liquidity estimation before profile generation."""

    asset: str = ""
    avg_volume: float = 0.0
    avg_price: float = 0.0
    avg_spread_bps: float = 0.0
    volatility: float = 0.0
    depth: float = 0.0
    confidence: float = 0.5


class LiquidityEstimator:
    """Estimates liquidity profiles from market data."""

    def __init__(self):
        self._profiles: Dict[str, LiquidityProfile] = {}

    def estimate(
        self,
        asset: str,
        avg_daily_volume: float = 0.0,
        avg_price: float = 0.0,
        avg_spread_bps: float = 0.0,
        volatility: float = 0.0,
        venue: str = "",
    ) -> LiquidityProfile:
        """Create liquidity profile from market data."""
        notional = avg_daily_volume * avg_price

        # Liquidity score (0-100)
        score = 50.0
        if notional > 1_000_000_000:    # >$1B daily
            score = 95.0
        elif notional > 100_000_000:     # >$100M daily
            score = 80.0
        elif notional > 10_000_000:      # >$10M daily
            score = 60.0
        elif notional > 1_000_000:
            score = 40.0
        else:
            score = 20.0

        # Adjust for spread
        if avg_spread_bps > 100:
            score *= 0.5
        elif avg_spread_bps > 50:
            score *= 0.7
        elif avg_spread_bps > 10:
            score *= 0.9

        # Adjust for volatility
        if volatility > 0.60:
            score *= 0.6
        elif volatility > 0.30:
            score *= 0.8

        # Tier
        if score >= 80:
            tier = "LARGE"
        elif score >= 55:
            tier = "MID"
        elif score >= 30:
            tier = "SMALL"
        else:
            tier = "ILLIQUID"

        # Participation limit varies by tier
        participation_map = {"LARGE": 0.10, "MID": 0.07, "SMALL": 0.04, "ILLIQUID": 0.02}
        participation_limit = participation_map.get(tier, 0.05)

        profile = LiquidityProfile(
            asset=asset,
            venue=venue,
            avg_daily_volume=avg_daily_volume,
            avg_daily_notional=notional,
            avg_spread_bps=avg_spread_bps,
            avg_price=avg_price,
            volatility=volatility,
            liquidity_score=min(100, max(0, score)),
            participation_limit=participation_limit,
            max_single_order_pct=participation_limit * 0.5,
            liquidity_tier=tier,
        )

        self._profiles[asset] = profile
        return profile

    def get(self, asset: str) -> Optional[LiquidityProfile]:
        return self._profiles.get(asset)

    def all_tiers(self) -> Dict[str, List[str]]:
        tiers: Dict[str, List[str]] = {"LARGE": [], "MID": [], "SMALL": [], "ILLIQUID": []}
        for asset, p in self._profiles.items():
            tiers[p.liquidity_tier].append(asset)
        return tiers
