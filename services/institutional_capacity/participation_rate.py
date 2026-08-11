"""
Participation Rate — Models and enforces market participation limits.

Participation Rate = Order Volume / Market Volume.

Ensures iceberg execution — never consuming too much of available
liquidity in any single time window.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ParticipationRate:
    """Participation rate assessment for an order in market context."""

    rate_id: str = field(default_factory=lambda: f"PR-{uuid.uuid4().hex[:8]}")
    asset: str = ""

    order_size: float = 0.0
    market_volume: float = 0.0           # e.g. daily volume
    interval_volume: float = 0.0          # e.g. 5-min volume

    participation_rate: float = 0.0       # order / interval_volume
    daily_participation: float = 0.0      # order / daily_volume

    limit: float = 0.10

    compliant: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rate_id": self.rate_id,
            "asset": self.asset,
            "participation_rate": self.participation_rate,
            "daily_participation": self.daily_participation,
            "limit": self.limit,
            "compliant": self.compliant,
        }


class ParticipationModel:
    """Models participation rate limits for execution."""

    def __init__(self, default_limit: float = 0.10):
        self.default_limit = default_limit

    def assess(
        self, asset: str, order_size: float, interval_volume: float, daily_volume: float = 0.0
    ) -> ParticipationRate:
        pr = ParticipationRate(
            asset=asset,
            order_size=order_size,
            market_volume=daily_volume,
            interval_volume=interval_volume,
            limit=self.default_limit,
        )

        if interval_volume > 0:
            pr.participation_rate = order_size / interval_volume
        if daily_volume > 0:
            pr.daily_participation = order_size / daily_volume

        pr.compliant = pr.participation_rate <= pr.limit

        return pr

    def max_order_size(self, interval_volume: float, limit: Optional[float] = None) -> float:
        rate = limit or self.default_limit
        return interval_volume * rate

    def resize(self, order_size: float, interval_volume: float, limit: Optional[float] = None) -> float:
        """Resize to be compliant."""
        max_size = self.max_order_size(interval_volume, limit)
        return min(order_size, max_size)
