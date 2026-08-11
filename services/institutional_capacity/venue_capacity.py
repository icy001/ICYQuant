"""
Venue Capacity — Capacity modeling per trading venue/exchange.

Different venues have different liquidity profiles, fee structures,
and participation rules.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class VenueCapacity:
    """Capacity assessment for a specific trading venue."""

    venue_id: str = field(default_factory=lambda: f"VC-{uuid.uuid4().hex[:8]}")
    venue_name: str = ""
    venue_code: str = ""                # MIC code or exchange identifier

    # Venue characteristics
    market_share_pct: float = 0.0       # % of total volume
    avg_daily_volume: float = 0.0
    avg_daily_notional: float = 0.0

    # Fees
    maker_fee_bps: float = 0.0
    taker_fee_bps: float = 0.0
    rebate_bps: float = 0.0

    # Capacity
    participation_limit: float = 0.10
    daily_capacity: float = 0.0
    remaining_capacity: float = 0.0

    # Status
    is_dark_pool: bool = False
    requires_routing: bool = False
    active: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "venue_id": self.venue_id,
            "venue_name": self.venue_name,
            "market_share_pct": self.market_share_pct,
            "daily_capacity": self.daily_capacity,
            "participation_limit": self.participation_limit,
            "active": self.active,
        }

    def allocate_capacity(self, amount: float) -> bool:
        """Allocate venue capacity. Returns True if sufficient."""
        if amount > self.remaining_capacity:
            return False
        self.remaining_capacity -= amount
        return True

    def reset(self) -> None:
        self.daily_capacity = self.avg_daily_notional * self.participation_limit
        self.remaining_capacity = self.daily_capacity
