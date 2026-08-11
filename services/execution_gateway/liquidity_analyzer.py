"""Liquidity Analyzer — Real-time liquidity analysis for venue selection.

Analyzes available liquidity across venues to inform routing decisions.
Considers order book depth, spread, and market impact estimation.

Analysis Dimensions:
    - Order Book Depth (bid/ask levels)
    - Bid-Ask Spread
    - Market Impact Estimation
    - Liquidity Concentration
    - Time-of-Day Patterns

Usage::

    analyzer = LiquidityAnalyzer()
    scores = await analyzer.analyze(symbol, quantity, side, venues)
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Any, Optional

from services.execution_gateway.venue_registry import Venue

logger = logging.getLogger(__name__)


@dataclass
class LiquidityProfile:
    """Liquidity profile for a single venue.

    Attributes:
        venue: Venue name
        score: Aggregate liquidity score (0-1)
        depth_bps: Market depth at best price in bps of ADV
        spread_bps: Bid-ask spread in basis points
        market_impact_bps: Estimated market impact for given quantity
        fill_probability: Estimated fill probability (0-1)
        concentration: Liquidity concentration score
        timestamp: Analysis timestamp
    """

    venue: str = ""
    score: float = 0.0
    depth_bps: float = 0.0
    spread_bps: float = 0.0
    market_impact_bps: float = 0.0
    fill_probability: float = 0.0
    concentration: float = 0.5
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "venue": self.venue,
            "score": self.score,
            "depth_bps": self.depth_bps,
            "spread_bps": self.spread_bps,
            "market_impact_bps": self.market_impact_bps,
            "fill_probability": self.fill_probability,
            "concentration": self.concentration,
            "metadata": self.metadata,
        }


class LiquidityAnalyzer:
    """Real-time liquidity analyzer for venue comparison.

    Evaluates liquidity conditions across venues to produce
    comparable liquidity scores for routing decisions.

    Attributes:
        _depth_weight: Weight for depth in score computation
        _spread_weight: Weight for spread in score computation
        _impact_weight: Weight for market impact in score computation
        _profiles: Cached liquidity profiles
    """

    def __init__(self) -> None:
        self._depth_weight = 0.40
        self._spread_weight = 0.25
        self._impact_weight = 0.35
        self._profiles: dict[str, LiquidityProfile] = {}

    # ── Analysis ───────────────────────────────────────────────────

    async def analyze(
        self,
        symbol: str,
        quantity: float,
        side: str = "BUY",
        venues: Optional[list[Venue]] = None,
        order_book_data: Optional[dict[str, Any]] = None,
    ) -> dict[str, dict[str, Any]]:
        """Analyze liquidity across venues.

        Args:
            symbol: Trading symbol
            quantity: Order quantity
            side: BUY or SELL
            venues: Venues to analyze
            order_book_data: Optional real order book snapshots

        Returns:
            Dict of venue_name → liquidity metrics
        """
        if not venues:
            logger.warning("No venues provided for liquidity analysis")
            return {}

        results: dict[str, dict[str, Any]] = {}

        for venue in venues:
            # Get order book data for this venue (simulated or real)
            book = (order_book_data or {}).get(venue.name, {})

            profile = self._analyze_venue(
                venue=venue,
                symbol=symbol,
                quantity=quantity,
                side=side,
                order_book=book,
            )

            self._profiles[venue.name] = profile
            results[venue.name] = profile.to_dict()

        logger.debug(
            "Liquidity analysis for %s: %d venues, best=%.2f",
            symbol,
            len(results),
            max((p.score for p in self._profiles.values()), default=0.0),
        )

        return results

    def _analyze_venue(
        self,
        venue: Venue,
        symbol: str,
        quantity: float,
        side: str,
        order_book: dict[str, Any],
    ) -> LiquidityProfile:
        """Analyze liquidity for a single venue.

        Args:
            venue: Venue to analyze
            symbol: Trading symbol
            quantity: Order quantity
            side: BUY or SELL
            order_book: Order book snapshot

        Returns:
            LiquidityProfile
        """
        # Use real data if available, otherwise simulate from venue metrics
        depth_bps = order_book.get("depth_bps", self._estimate_depth(venue))
        spread_bps = order_book.get("spread_bps", self._estimate_spread(venue))

        # Estimate market impact using square-root model
        market_impact_bps = self._estimate_market_impact(
            quantity=quantity,
            venue=venue,
            depth_bps=depth_bps,
        )

        # Estimate fill probability
        fill_prob = self._estimate_fill_probability(
            quantity=quantity,
            depth_bps=depth_bps,
            side=side,
        )

        # Compute aggregate score
        depth_score = min(depth_bps / 100.0, 1.0)  # Normalize to 0-1
        spread_score = max(0.0, 1.0 - spread_bps / 10.0)  # 10bps spread → 0
        impact_score = max(0.0, 1.0 - market_impact_bps / 50.0)  # 50bps impact → 0

        score = (
            depth_score * self._depth_weight
            + spread_score * self._spread_weight
            + impact_score * self._impact_weight
        )

        return LiquidityProfile(
            venue=venue.name,
            score=min(max(score, 0.0), 1.0),
            depth_bps=depth_bps,
            spread_bps=spread_bps,
            market_impact_bps=market_impact_bps,
            fill_probability=fill_prob,
            concentration=0.5,  # Default moderate concentration
        )

    # ── Estimation Models ──────────────────────────────────────────

    def _estimate_depth(self, venue: Venue) -> float:
        """Estimate market depth from venue characteristics.

        Args:
            venue: Venue to estimate

        Returns:
            Estimated depth in bps of ADV
        """
        # Higher liquidity_score → more depth
        base_depth = venue.liquidity_score * 50.0
        # Exchange venues have more depth than dark pools
        type_multiplier = {
            "EXCHANGE": 1.5,
            "ECN": 1.2,
            "MTF": 1.0,
            "DARK_POOL": 0.6,
            "SDP": 0.8,
            "OTC": 0.5,
        }.get(venue.venue_type.value, 1.0)
        return base_depth * type_multiplier

    def _estimate_spread(self, venue: Venue) -> float:
        """Estimate bid-ask spread from venue characteristics.

        Args:
            venue: Venue to estimate

        Returns:
            Estimated spread in basis points
        """
        # Higher liquidity → tighter spread
        base_spread = (1.0 - venue.liquidity_score) * 10.0 + 1.0
        return base_spread

    def _estimate_market_impact(
        self,
        quantity: float,
        venue: Venue,
        depth_bps: float,
    ) -> float:
        """Estimate market impact using square-root model.

        Implements the standard square-root market impact model:
        Impact = sigma * sqrt(Q / ADV)

        Args:
            quantity: Order quantity
            venue: Target venue
            depth_bps: Market depth in bps

        Returns:
            Estimated market impact in bps
        """
        if quantity <= 0 or depth_bps <= 0:
            return 0.0

        # Participation rate proxy
        participation = min(quantity / max(depth_bps, 1.0), 1.0)

        # Square-root impact model
        sigma = 1.0  # Daily volatility proxy
        impact = sigma * math.sqrt(participation) * 100.0

        # Adjust for venue type
        type_multiplier = {
            "EXCHANGE": 1.0,
            "ECN": 1.0,
            "MTF": 1.1,
            "DARK_POOL": 0.5,
            "SDP": 1.2,
            "OTC": 1.5,
        }.get(venue.venue_type.value, 1.0)

        return impact * type_multiplier

    def _estimate_fill_probability(
        self,
        quantity: float,
        depth_bps: float,
        side: str,
    ) -> float:
        """Estimate fill probability.

        Args:
            quantity: Order quantity
            depth_bps: Market depth
            side: BUY or SELL

        Returns:
            Fill probability (0-1)
        """
        if depth_bps <= 0:
            return 0.0

        ratio = quantity / depth_bps

        if ratio <= 0.1:
            return 0.99
        elif ratio <= 0.5:
            return 0.85
        elif ratio <= 1.0:
            return 0.60
        elif ratio <= 2.0:
            return 0.30
        else:
            return 0.10

    # ── Query ──────────────────────────────────────────────────────

    def get_profile(self, venue_name: str) -> Optional[LiquidityProfile]:
        """Get cached liquidity profile.

        Args:
            venue_name: Venue name

        Returns:
            LiquidityProfile if cached
        """
        return self._profiles.get(venue_name)

    def compare_venues(self, venue_a: str, venue_b: str) -> dict[str, Any]:
        """Compare liquidity between two venues.

        Args:
            venue_a: First venue name
            venue_b: Second venue name

        Returns:
            Comparison dictionary
        """
        profile_a = self._profiles.get(venue_a)
        profile_b = self._profiles.get(venue_b)

        if not profile_a or not profile_b:
            return {"error": "One or both venues not analyzed"}

        return {
            "venue_a": {"name": venue_a, "score": profile_a.score},
            "venue_b": {"name": venue_b, "score": profile_b.score},
            "better": venue_a if profile_a.score >= profile_b.score else venue_b,
            "score_delta": profile_a.score - profile_b.score,
        }

    def to_dict(self) -> dict[str, Any]:
        """Serialize analyzer state."""
        return {
            "profiles_count": len(self._profiles),
            "weights": {
                "depth": self._depth_weight,
                "spread": self._spread_weight,
                "impact": self._impact_weight,
            },
        }
