"""
Asset Capacity — Per-asset capacity modeling and limits.

Single asset capacity = ADVolume * participation_limit, adjusted for
volatility, spread, and current book depth.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class AssetCapacity:
    """Capacity assessment for a single trading asset."""

    capacity_id: str = field(default_factory=lambda: f"AC-{uuid.uuid4().hex[:8]}")
    asset: str = ""

    # Volume-based
    avg_daily_volume: float = 0.0       # shares
    avg_daily_notional: float = 0.0     # dollar

    # Capacity limits
    max_participation_rate: float = 0.10
    daily_capacity: float = 0.0          # max notional per day
    single_order_capacity: float = 0.0   # max notional per order

    # Adjustments
    volatility_adjustment: float = 1.0
    spread_adjustment: float = 1.0
    regime_adjustment: float = 1.0

    # Current
    used_today: float = 0.0
    remaining_today: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "capacity_id": self.capacity_id,
            "asset": self.asset,
            "avg_daily_notional": self.avg_daily_notional,
            "daily_capacity": self.daily_capacity,
            "single_order_capacity": self.single_order_capacity,
            "used_today": self.used_today,
            "remaining_today": self.remaining_today,
        }

    def compute(
        self,
        avg_daily_volume: float = 0.0,
        avg_price: float = 0.0,
        max_participation: float = 0.10,
        volatility: float = 0.0,
        spread_bps: float = 0.0,
        regime_multiplier: float = 1.0,
    ) -> None:
        self.avg_daily_volume = avg_daily_volume
        self.avg_daily_notional = avg_daily_volume * avg_price

        # Volatility adjustment
        if volatility > 0.50:
            self.volatility_adjustment = 0.5
        elif volatility > 0.30:
            self.volatility_adjustment = 0.7
        else:
            self.volatility_adjustment = 1.0

        # Spread adjustment
        if spread_bps > 100:
            self.spread_adjustment = 0.3
        elif spread_bps > 50:
            self.spread_adjustment = 0.6
        else:
            self.spread_adjustment = 1.0

        self.regime_adjustment = regime_multiplier

        effective_rate = max_participation * self.volatility_adjustment * self.spread_adjustment * regime_multiplier
        self.max_participation_rate = effective_rate
        self.daily_capacity = self.avg_daily_notional * effective_rate
        self.single_order_capacity = self.daily_capacity * 0.3
        self.remaining_today = self.daily_capacity - self.used_today

    def consume(self, amount: float) -> bool:
        """Attempt to reserve capacity."""
        if amount <= self.remaining_today:
            self.used_today += amount
            self.remaining_today = self.daily_capacity - self.used_today
            return True
        return False

    def reset_daily(self) -> None:
        self.used_today = 0.0
        self.remaining_today = self.daily_capacity
