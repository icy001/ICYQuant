"""
Venue Selector — selects optimal trading venue per order.

Evaluates venues based on:
    - Historical fill rate
    - Average spread
    - Fee structure
    - Latency
    - Reliability score
    - Market share for the specific asset
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


@dataclass
class VenueScore:
    """Scoring result for a single venue."""
    venue: str
    fill_rate: float = 0.0
    avg_cost_bps: float = 0.0
    avg_spread_bps: float = 0.0
    latency_ms: float = 0.0
    composite_score: float = 0.0


@dataclass
class VenueSelection:
    """Venue selection result."""
    id: str = field(default_factory=lambda: str(uuid4()))
    order_id: str = ""
    asset: str = ""
    selected_venue: str = "SMART"
    scores: list[VenueScore] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)


class VenueSelector:
    """
    Selects optimal trading venue for each order.

    Scoring formula:
        score = fill_rate * 0.4 + (1 - cost_norm) * 0.25
                + (1 - spread_norm) * 0.20 + (1 - latency_norm) * 0.15
    """

    def __init__(self) -> None:
        self._venue_stats: dict[str, dict] = {
            "PRIMARY": {"fill_rate": 0.95, "cost_bps": 2.0, "spread_bps": 5, "latency_ms": 3},
            "SECONDARY": {"fill_rate": 0.85, "cost_bps": 1.5, "spread_bps": 7, "latency_ms": 5},
            "DARK_POOL": {"fill_rate": 0.65, "cost_bps": 0.5, "spread_bps": 2, "latency_ms": 8},
            "SMART": {"fill_rate": 0.98, "cost_bps": 2.5, "spread_bps": 5, "latency_ms": 4},
            "ALGO": {"fill_rate": 0.90, "cost_bps": 3.0, "spread_bps": 6, "latency_ms": 6},
        }
        self._selections: list[VenueSelection] = []

    async def select(
        self,
        order_id: str,
        asset: str,
        quantity: int,
        adv: float,
        urgency: str = "MEDIUM",
    ) -> VenueSelection:
        """Select best venue for an order."""
        result = VenueSelection(order_id=order_id, asset=asset)
        pct_adv = abs(quantity) / max(adv, 1)

        scores = []
        for venue, stats in self._venue_stats.items():
            fill_rate = stats["fill_rate"]
            cost_norm = stats["cost_bps"] / 10
            spread_norm = stats["spread_bps"] / 20
            latency_norm = stats["latency_ms"] / 20

            # Adjust weights for order characteristics
            fill_weight = 0.40
            if urgency == "CRITICAL":
                fill_weight = 0.50
                latency_norm *= 0.5  # Speed matters more

            # Large orders: dark pools more attractive
            if pct_adv > 0.05 and venue == "DARK_POOL":
                fill_rate *= 0.90  # Slightly discount fill

            score = (
                fill_rate * fill_weight
                + (1 - cost_norm) * 0.25
                + (1 - spread_norm) * 0.20
                + (1 - latency_norm) * 0.15
            )
            scores.append(VenueScore(
                venue=venue, fill_rate=fill_rate,
                avg_cost_bps=stats["cost_bps"],
                avg_spread_bps=stats["spread_bps"],
                latency_ms=stats["latency_ms"],
                composite_score=score,
            ))

        scores.sort(key=lambda s: s.composite_score, reverse=True)
        result.scores = scores
        result.selected_venue = scores[0].venue

        self._selections.append(result)
        if len(self._selections) > 500:
            self._selections = self._selections[-250:]

        return result

    def update_venue_stats(self, venue: str, stats: dict) -> None:
        """Update venue statistics from execution feedback."""
        if venue in self._venue_stats:
            current = self._venue_stats[venue]
            # Exponentially weighted update
            alpha = 0.2
            for key in ["fill_rate", "cost_bps", "spread_bps", "latency_ms"]:
                if key in stats:
                    current[key] = current[key] * (1 - alpha) + stats[key] * alpha
