"""Liquidity Model — market liquidity estimation for trade execution.

Estimates fillable volume based on ADV, bid/ask spread,
participation rate, and order book depth to prevent
unrealistic large fills in backtests.

Metrics::

    ADV → Bid/Ask Spread → Participation Rate → Order Book Depth
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class LiquidityProfile:
    """Liquidity metrics for a single symbol."""

    symbol: str = ""
    adv: float = 0.0  # average daily volume (shares)
    adv_value: float = 0.0  # average daily volume (notional)
    spread_bps: float = 0.0  # bid-ask spread in bps
    depth_bid: float = 0.0  # shares available at best bid
    depth_ask: float = 0.0  # shares available at best ask
    turnover_rate: float = 0.0  # daily turnover vs float
    market_cap: float = 0.0
    is_liquid: bool = True


class LiquidityModel:
    """Market liquidity model for realistic execution simulation.

    Estimates how much volume can be filled at current market conditions,
    preventing unrealistic execution of large orders in illiquid names.

    Usage::

        lm = LiquidityModel(max_participation=0.1)
        fillable = await lm.get_fillable_volume("000001.SZ", 50000, market_data)
    """

    def __init__(
        self,
        max_participation_rate: float = 0.1,  # 10% of ADV
        min_spread_bps: float = 0.1,
        max_spread_bps: float = 50.0,
    ) -> None:
        self._max_participation_rate = max_participation_rate
        self._min_spread_bps = min_spread_bps
        self._max_spread_bps = max_spread_bps
        self._profiles: Dict[str, LiquidityProfile] = {}

    # ── estimation ─────────────────────────────────────────────────────────

    async def get_fillable_volume(
        self,
        symbol: str,
        desired_volume: float,
        market_data: Dict[str, Any],
        participation_rate: Optional[float] = None,
    ) -> float:
        """Estimate how much volume can be filled.

        Args:
            symbol: Ticker symbol.
            desired_volume: Requested order size.
            market_data: Current market data (OHLCV).
            participation_rate: Override max participation rate.

        Returns:
            Estimated fillable volume.
        """
        adv = market_data.get("volume", 0)
        # If ADV is volume of current bar, scale to daily estimate
        if adv < desired_volume:
            adv = max(adv, desired_volume / 0.1)  # assume at least 10x

        max_allowed = adv * (participation_rate or self._max_participation_rate)
        fillable = min(desired_volume, max_allowed)

        return fillable

    async def estimate_spread(
        self,
        symbol: str,
        market_data: Dict[str, Any],
    ) -> float:
        """Estimate bid-ask spread in bps.

        Uses high-low range as a proxy when explicit
        bid/ask data is not available.
        """
        price = market_data.get("close", 0)
        if price <= 0:
            return self._min_spread_bps

        # If bid/ask available, use directly
        bid = market_data.get("bid")
        ask = market_data.get("ask")
        if bid and ask:
            return (ask - bid) / price * 10000

        # Fallback: estimate from high-low range
        high = market_data.get("high", price)
        low = market_data.get("low", price)
        if high > low:
            spread = (high - low) / price * 10000
            return max(self._min_spread_bps, min(spread, self._max_spread_bps))

        return self._min_spread_bps

    async def estimate_liquidity_score(
        self,
        symbol: str,
        market_data: Dict[str, Any],
    ) -> float:
        """Estimate a liquidity score (0.0 = illiquid, 1.0 = highly liquid).

        Based on:
        * Volume relative to desired size
        * Spread tightness
        * Price level (not penny stocks)
        """
        volume = market_data.get("volume", 0)
        price = market_data.get("close", 0)

        score = 0.0

        # Volume score: log scale
        if volume > 0:
            score += min(1.0, volume / 1_000_000) * 0.4

        # Price score: not penny stock
        if price > 5:
            score += 0.3
        elif price > 1:
            score += 0.15

        # Spread score
        spread = await self.estimate_spread(symbol, market_data)
        spread_score = max(0, 1 - spread / 50) * 0.3  # 50bps = 0 score
        score += spread_score

        return min(1.0, score)

    # ── profile management ─────────────────────────────────────────────────

    async def update_profile(
        self, symbol: str, profile: LiquidityProfile
    ) -> None:
        """Update liquidity profile for a symbol."""
        self._profiles[symbol] = profile

    async def get_profile(self, symbol: str) -> Optional[LiquidityProfile]:
        """Get liquidity profile for a symbol."""
        return self._profiles.get(symbol)

    async def is_liquid(
        self,
        symbol: str,
        desired_volume: float,
        market_data: Dict[str, Any],
    ) -> bool:
        """Check if a symbol is liquid enough for the desired volume."""
        fillable = await self.get_fillable_volume(symbol, desired_volume, market_data)
        return fillable >= desired_volume * 0.9  # 90%+ fillable = liquid

    # ── configuration ──────────────────────────────────────────────────────

    def set_max_participation(self, rate: float) -> None:
        """Set maximum participation rate."""
        self._max_participation_rate = rate

    def get_stats(self) -> Dict[str, Any]:
        """Return liquidity model statistics."""
        profiles = self._profiles
        return {
            "max_participation_rate": self._max_participation_rate,
            "profiles_count": len(profiles),
            "avg_spread_bps": (
                sum(p.spread_bps for p in profiles.values()) / len(profiles)
                if profiles else 0
            ),
            "avg_adv": (
                sum(p.adv_value for p in profiles.values()) / len(profiles)
                if profiles else 0
            ),
        }
