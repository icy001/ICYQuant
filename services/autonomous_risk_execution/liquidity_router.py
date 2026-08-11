"""
Liquidity Router — routes orders to optimal venues based on liquidity.

Considers:
    - Venue liquidity profile (ADV, depth, spread)
    - Fee structure
    - Fill probability
    - Latency
    - Venue reliability
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


@dataclass
class VenueInfo:
    """Information about a trading venue."""
    name: str
    liquidity_score: float = 1.0
    avg_spread_bps: float = 3.0
    depth_score: float = 1.0
    fee_bps: float = 0.5
    fill_probability: float = 0.95
    latency_ms: float = 5.0
    reliability: float = 0.999


@dataclass
class RouteDecision:
    """Routing decision for an order."""
    id: str = field(default_factory=lambda: str(uuid4()))
    order_id: str = ""
    venue: str = "SMART"
    quantity: int = 0
    expected_fill_rate: float = 0.95
    expected_cost_bps: float = 0.0
    reason: str = ""
    timestamp: datetime = field(default_factory=datetime.now)


class LiquidityRouter:
    """
    Routes orders to optimal venues.

    Venue scoring formula:
        score = w1 * liquidity + w2 * (1 - spread_norm) + w3 * fill_prob
                - w4 * fee_norm - w5 * latency_norm

    Default venue hierarchy:
        1. SMART (aggregated best execution)
        2. PRIMARY exchange
        3. SECONDARY/DARK pools (for large orders)
    """

    DEFAULT_VENUES: dict[str, VenueInfo] = {
        "PRIMARY": VenueInfo("PRIMARY", liquidity_score=1.0, fee_bps=0.5),
        "SECONDARY": VenueInfo("SECONDARY", liquidity_score=0.7, fee_bps=0.3),
        "DARK_POOL": VenueInfo("DARK_POOL", liquidity_score=0.5, fee_bps=0.1,
                               fill_probability=0.70),
        "SMART": VenueInfo("SMART", liquidity_score=1.0, fee_bps=0.5,
                          fill_probability=0.98),
    }

    def __init__(self, venues: Optional[dict[str, VenueInfo]] = None) -> None:
        self._venues = venues or dict(self.DEFAULT_VENUES)
        self._route_history: list[RouteDecision] = []

    async def route(
        self,
        order_id: str,
        asset: str,
        quantity: int,
        adv: float,
        strategy: str = "VWAP",
    ) -> RouteDecision:
        """
        Determine optimal venue for an order.

        Logic:
            - Small orders: SMART or PRIMARY
            - Large orders (high %ADV): consider DARK_POOL
            - High urgency: SMART
            - Low urgency: PRICE improvement focus
        """
        pct_adv = abs(quantity) / max(adv, 1)

        # Score each venue
        scores = {}
        for name, venue in self._venues.items():
            # Higher weight on liquidity for large orders
            liq_weight = min(1.0, 0.5 + pct_adv * 0.5)
            # Higher weight on fill prob for urgent orders
            fill_weight = 0.5

            score = (
                venue.liquidity_score * liq_weight * 0.35
                + venue.fill_probability * fill_weight * 0.35
                + (1 - venue.fee_bps / 10) * 0.15
                + venue.reliability * 0.15
            )
            scores[name] = score

        best_venue = max(scores, key=scores.get)

        decision = RouteDecision(
            order_id=order_id,
            venue=best_venue,
            quantity=quantity,
            expected_fill_rate=self._venues[best_venue].fill_probability,
            expected_cost_bps=self._venues[best_venue].fee_bps,
            reason=f"Score={scores[best_venue]:.3f} pctADV={pct_adv:.1%}",
        )
        self._route_history.append(decision)
        if len(self._route_history) > 500:
            self._route_history = self._route_history[-250:]

        return decision

    def add_venue(self, name: str, info: VenueInfo) -> None:
        """Register a venue."""
        self._venues[name] = info

    def get_venue(self, name: str) -> Optional[VenueInfo]:
        return self._venues.get(name)

    @property
    def route_history(self) -> list[RouteDecision]:
        return self._route_history[-100:]
