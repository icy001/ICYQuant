"""
Impact Budget — Per-portfolio market impact spending limit.

Example: max expected impact = 15 bps.
If new order would cause 24 bps → RESIZE or SPLIT.

Prevents death-by-a-thousand-cuts from incremental impact.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ImpactBudget:
    """Market impact budget for a portfolio or strategy."""

    budget_id: str = field(default_factory=lambda: f"IB-{uuid.uuid4().hex[:8]}")
    name: str = ""

    # Limits
    max_impact_bps: float = 15.0         # total portfolio
    max_per_order_bps: float = 5.0       # per individual order
    max_per_asset_bps: float = 8.0       # per asset daily

    # Current
    spent_today_bps: float = 0.0
    remaining_bps: float = 0.0

    # Per-asset tracking
    asset_spending: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "budget_id": self.budget_id,
            "name": self.name,
            "max_impact_bps": self.max_impact_bps,
            "spent_today_bps": self.spent_today_bps,
            "remaining_bps": self.remaining_bps,
        }

    def check_order(self, asset: str, estimated_impact_bps: float) -> bool:
        """Check if an order's impact fits within budget."""
        if estimated_impact_bps > self.max_per_order_bps:
            return False
        asset_spent = self.asset_spending.get(asset, 0.0)
        if asset_spent + estimated_impact_bps > self.max_per_asset_bps:
            return False
        if self.spent_today_bps + estimated_impact_bps > self.max_impact_bps:
            return False
        return True

    def consume(self, asset: str, impact_bps: float) -> bool:
        """Consume impact budget. Returns True if within limits."""
        if not self.check_order(asset, impact_bps):
            return False
        self.asset_spending[asset] = self.asset_spending.get(asset, 0.0) + impact_bps
        self.spent_today_bps += impact_bps
        self.remaining_bps = self.max_impact_bps - self.spent_today_bps
        return True

    def reset(self) -> None:
        self.spent_today_bps = 0.0
        self.remaining_bps = self.max_impact_bps
        self.asset_spending.clear()

    @property
    def utilization(self) -> float:
        return self.spent_today_bps / max(self.max_impact_bps, 1e-6)
