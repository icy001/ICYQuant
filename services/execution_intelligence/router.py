from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class VenueType(str, Enum):
    EXCHANGE = "EXCHANGE"
    DARK_POOL = "DARK_POOL"
    ECN = "ECN"
    BROKER_ALGO = "BROKER_ALGO"
    SOR = "SOR"  # Smart Order Router
    MTF = "MTF"  # Multilateral Trading Facility


class RouteStrategy(str, Enum):
    BEST_PRICE = "BEST_PRICE"
    MIN_IMPACT = "MIN_IMPACT"
    MAX_FILL = "MAX_FILL"
    LOWEST_COST = "LOWEST_COST"
    LATENCY_SENSITIVE = "LATENCY_SENSITIVE"


@dataclass
class Venue:
    name: str
    venue_type: VenueType
    latency_ms: float
    fee_bps: float
    fill_rate: float
    dark_liquidity: float = 0.0
    active: bool = True


@dataclass
class RouteDecision:
    venue: Venue
    allocation_pct: float
    reason: str = ""
    estimated_cost_bps: float = 0.0


@dataclass
class RoutingPlan:
    order_id: str
    strategy: RouteStrategy
    decisions: List[RouteDecision] = field(default_factory=list)
    total_estimated_cost_bps: float = 0.0


class SmartOrderRouter:
    """Smart Order Routing Engine - routes orders to optimal venues."""

    def __init__(self):
        self.venues: List[Venue] = []
        self._init_default_venues()

    def _init_default_venues(self):
        self.venues = [
            Venue(name="NASDAQ", venue_type=VenueType.EXCHANGE, latency_ms=1.0, fee_bps=0.30, fill_rate=0.95),
            Venue(name="NYSE", venue_type=VenueType.EXCHANGE, latency_ms=1.5, fee_bps=0.25, fill_rate=0.93),
            Venue(name="IEX", venue_type=VenueType.EXCHANGE, latency_ms=2.0, fee_bps=0.20, fill_rate=0.90),
            Venue(name="DarkPool-A", venue_type=VenueType.DARK_POOL, latency_ms=5.0, fee_bps=0.10, fill_rate=0.60, dark_liquidity=0.3),
            Venue(name="ECN-X", venue_type=VenueType.ECN, latency_ms=0.5, fee_bps=0.35, fill_rate=0.88),
        ]

    def route(self, order):
        """Route an order to the optimal venue(s).

        Args:
            order: Order to route - can be RoutingPlan dataclass or dict/symbol.

        Returns:
            Dict containing routing plan.
        """
        if isinstance(order, RoutingPlan):
            return self._route_with_plan(order)
        return {"route": order}

    def _route_with_plan(self, order: RoutingPlan) -> dict:
        decisions = self._select_venues(order.strategy, order.order_id)
        total_cost = sum(d.estimated_cost_bps * d.allocation_pct for d in decisions)
        return {
            "route": {
                "order_id": order.order_id,
                "strategy": order.strategy.value,
                "venues": [
                    {
                        "venue": d.venue.name,
                        "allocation_pct": d.allocation_pct,
                        "reason": d.reason,
                        "estimated_cost_bps": d.estimated_cost_bps,
                    }
                    for d in decisions
                ],
                "total_estimated_cost_bps": round(total_cost, 2),
            }
        }

    def _select_venues(self, strategy: RouteStrategy, order_id: str) -> List[RouteDecision]:
        active_venues = [v for v in self.venues if v.active]

        if strategy == RouteStrategy.BEST_PRICE:
            return self._best_price_routing(active_venues)
        elif strategy == RouteStrategy.MIN_IMPACT:
            return self._min_impact_routing(active_venues)
        elif strategy == RouteStrategy.MAX_FILL:
            return self._max_fill_routing(active_venues)
        elif strategy == RouteStrategy.LOWEST_COST:
            return self._lowest_cost_routing(active_venues)
        else:
            return self._best_price_routing(active_venues)

    def _best_price_routing(self, venues: List[Venue]) -> List[RouteDecision]:
        sorted_venues = sorted(venues, key=lambda v: v.latency_ms)
        return [
            RouteDecision(
                venue=sorted_venues[0],
                allocation_pct=0.6,
                reason="Best price - lowest latency",
                estimated_cost_bps=sorted_venues[0].fee_bps,
            ),
            RouteDecision(
                venue=sorted_venues[1] if len(sorted_venues) > 1 else sorted_venues[0],
                allocation_pct=0.4,
                reason="Secondary venue for overflow",
                estimated_cost_bps=sorted_venues[1].fee_bps if len(sorted_venues) > 1 else 0,
            ),
        ]

    def _min_impact_routing(self, venues: List[Venue]) -> List[RouteDecision]:
        dark_pools = [v for v in venues if v.venue_type == VenueType.DARK_POOL]
        exchanges = [v for v in venues if v.venue_type == VenueType.EXCHANGE]
        decisions = []
        if dark_pools:
            decisions.append(
                RouteDecision(venue=dark_pools[0], allocation_pct=0.5, reason="Dark pool for minimal impact", estimated_cost_bps=dark_pools[0].fee_bps)
            )
        if exchanges:
            remaining = 1.0 - sum(d.allocation_pct for d in decisions)
            decisions.append(
                RouteDecision(venue=exchanges[0], allocation_pct=remaining, reason="Exchange for remaining", estimated_cost_bps=exchanges[0].fee_bps)
            )
        return decisions

    def _max_fill_routing(self, venues: List[Venue]) -> List[RouteDecision]:
        sorted_venues = sorted(venues, key=lambda v: v.fill_rate, reverse=True)
        return [
            RouteDecision(
                venue=sorted_venues[0],
                allocation_pct=0.5,
                reason=f"Highest fill rate: {sorted_venues[0].fill_rate}",
                estimated_cost_bps=sorted_venues[0].fee_bps,
            ),
            RouteDecision(
                venue=sorted_venues[1] if len(sorted_venues) > 1 else sorted_venues[0],
                allocation_pct=0.5,
                reason="Secondary for fill assurance",
                estimated_cost_bps=sorted_venues[1].fee_bps if len(sorted_venues) > 1 else 0,
            ),
        ]

    def _lowest_cost_routing(self, venues: List[Venue]) -> List[RouteDecision]:
        sorted_venues = sorted(venues, key=lambda v: v.fee_bps)
        return [
            RouteDecision(
                venue=sorted_venues[0],
                allocation_pct=1.0,
                reason=f"Lowest fee: {sorted_venues[0].fee_bps} bps",
                estimated_cost_bps=sorted_venues[0].fee_bps,
            )
        ]

    def add_venue(self, venue: Venue):
        """Register a new trading venue."""
        self.venues.append(venue)
