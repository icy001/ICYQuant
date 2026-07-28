"""Smart Routing Engine – intelligent venue selection for order execution."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .order import ExecutionOrder


@dataclass
class Venue:
    """A trading venue / exchange with its characteristics."""

    name: str
    liquidity_score: float = 1.0  # 0-1 scale
    spread_bps: float = 0.0
    fee_bps: float = 0.0
    latency_ms: float = 0.0
    market_depth: float = 1.0  # 0-1 scale

    def composite_score(self) -> float:
        """Compute a composite quality score for this venue.

        Higher liquidity + depth + lower spread/fee/latency → higher score.
        """
        score = (
            self.liquidity_score * 0.30
            + self.market_depth * 0.25
            + (1.0 - min(self.spread_bps / 100.0, 1.0)) * 0.20
            + (1.0 - min(self.fee_bps / 50.0, 1.0)) * 0.15
            + (1.0 - min(self.latency_ms / 100.0, 1.0)) * 0.10
        )
        return round(score, 4)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "liquidity_score": self.liquidity_score,
            "spread_bps": self.spread_bps,
            "fee_bps": self.fee_bps,
            "latency_ms": self.latency_ms,
            "market_depth": self.market_depth,
            "composite_score": self.composite_score(),
        }


class SmartRoutingEngine:
    """Selects the optimal execution venue for each order.

    Evaluates available venues by liquidity, spread, fees, latency,
    and market depth. Returns the venue with the highest composite
    score, optionally splitting across multiple venues for large orders.
    """

    def __init__(self, venues: Optional[List[Venue]] = None):
        self.venues = venues if venues is not None else self._default_venues()

    @staticmethod
    def _default_venues() -> List[Venue]:
        """Provide a default set of simulated venues."""
        return [
            Venue(name="Primary_Exchange", liquidity_score=0.95,
                  spread_bps=1.0, fee_bps=2.0, latency_ms=1.0,
                  market_depth=0.90),
            Venue(name="Dark_Pool_A", liquidity_score=0.70,
                  spread_bps=0.5, fee_bps=1.0, latency_ms=5.0,
                  market_depth=0.60),
            Venue(name="Dark_Pool_B", liquidity_score=0.60,
                  spread_bps=0.8, fee_bps=1.5, latency_ms=8.0,
                  market_depth=0.50),
            Venue(name="Alternative_Exchange", liquidity_score=0.80,
                  spread_bps=2.0, fee_bps=3.0, latency_ms=3.0,
                  market_depth=0.70),
        ]

    def route(self, order: ExecutionOrder) -> dict:
        """Route an order to the best venue.

        Returns a dict with the selected venue and routing metadata.
        For large orders, may recommend splitting across multiple venues.
        """
        if not self.venues:
            return {"venue": "best_market", "split": []}

        best = self._select_best_venue()
        split = self._split_plan(order) if order.quantity > 5000 else []

        return {
            "venue": best.name if best else "best_market",
            "composite_score": best.composite_score() if best else 1.0,
            "split": split,
            "reason": self._routing_reason(best, order),
        }

    def _select_best_venue(self) -> Optional[Venue]:
        """Pick the venue with the highest composite score."""
        if not self.venues:
            return None
        return max(self.venues, key=lambda v: v.composite_score())

    def _split_plan(self, order: ExecutionOrder) -> List[dict]:
        """Create a multi-venue split plan for large orders."""
        best = self._select_best_venue()
        if best is None:
            return []

        # Simple split: 70% primary venue, 30% dark pool
        primary_qty = int(order.quantity * 0.70)
        dark_qty = order.quantity - primary_qty

        plan = [{"venue": best.name, "quantity": primary_qty, "share": 0.70}]

        # Find a suitable dark pool for the remainder
        dark_venue = next((v for v in self.venues
                           if "Dark" in v.name and v != best), None)
        if dark_venue:
            plan.append({"venue": dark_venue.name, "quantity": dark_qty,
                         "share": 0.30})
        else:
            plan[0]["quantity"] = order.quantity
            plan[0]["share"] = 1.0

        return plan

    def _routing_reason(self, venue: Optional[Venue],
                        order: ExecutionOrder) -> str:
        """Generate a human-readable routing decision explanation."""
        if venue is None:
            return "No venue available – default routing."
        parts = [f"Selected {venue.name}"]
        parts.append(f"(liquidity={venue.liquidity_score:.0%}, "
                     f"depth={venue.market_depth:.0%}, "
                     f"spread={venue.spread_bps}bps)")
        if order.quantity > 5000:
            parts.append("– large order, splitting across venues.")
        return " ".join(parts)

    def list_venues(self) -> List[dict]:
        """Return all venues with their composite scores."""
        return [v.to_dict() for v in self.venues]

    def add_venue(self, venue: Venue) -> None:
        """Register a new venue."""
        self.venues.append(venue)
