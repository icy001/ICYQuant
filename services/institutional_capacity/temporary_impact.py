"""
Temporary Impact — Transient price impact during order execution.

Consumes liquidity → price moves against order → partially recovers after completion.
Models: immediate execution cost that reverts after the order passes.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class TemporaryImpact:
    """Temporary (transient) market impact of an order."""

    impact_id: str = field(default_factory=lambda: f"TI-{uuid.uuid4().hex[:8]}")
    asset: str = ""
    order_size: float = 0.0
    interval_volume: float = 0.0         # volume during execution window

    # Model
    participation: float = 0.0           # order / interval_volume
    estimated_impact_bps: float = 0.0
    recovery_time_seconds: float = 0.0   # time to recover 50% of impact

    # Cost
    cost_bps: float = 0.0
    cost_dollars: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "impact_id": self.impact_id,
            "asset": self.asset,
            "participation": self.participation,
            "estimated_impact_bps": self.estimated_impact_bps,
            "recovery_time_seconds": self.recovery_time_seconds,
            "cost_dollars": self.cost_dollars,
        }

    def estimate(self, volatility: float = 0.0, scale: float = 1.0) -> "TemporaryImpact":
        """Square-root temporary impact: σ * scale * (Q/V_int)^0.5 * 0.6"""
        if self.interval_volume <= 0:
            return self

        self.participation = self.order_size / self.interval_volume
        self.estimated_impact_bps = volatility * scale * (self.participation ** 0.5) * 10000 * 0.6
        self.cost_bps = self.estimated_impact_bps
        self.cost_dollars = self.order_size * self.estimated_impact_bps / 10000

        # Recovery time roughly proportional to participation
        self.recovery_time_seconds = self.participation * 600  # ~10min for 1% part

        return self
