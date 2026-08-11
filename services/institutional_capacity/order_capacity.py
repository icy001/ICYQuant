"""
Order Capacity — Per-order capacity constraints and validation.

Ensures individual orders respect participation limits, venue caps,
and instrument-specific constraints.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class OrderCapacity:
    """Capacity assessment for a single order."""

    order_capacity_id: str = field(default_factory=lambda: f"OC-{uuid.uuid4().hex[:8]}")

    asset: str = ""
    side: str = "BUY"

    requested_size: float = 0.0
    approved_size: float = 0.0

    # Constraints
    max_size_by_participation: float = 0.0
    max_size_by_venue: float = 0.0
    max_size_by_impact: float = 0.0

    # Limit
    effective_limit: float = 0.0         # MIN of all constraints
    status: str = "PENDING"              # PENDING, APPROVED, RESIZED, SPLIT, REJECTED

    # Splitting
    needs_split: bool = False
    split_sizes: List[float] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "order_capacity_id": self.order_capacity_id,
            "asset": self.asset,
            "side": self.side,
            "requested_size": self.requested_size,
            "approved_size": self.approved_size,
            "status": self.status,
            "needs_split": self.needs_split,
        }

    def compute_limit(self) -> float:
        limits = [l for l in [self.max_size_by_participation, self.max_size_by_venue, self.max_size_by_impact] if l > 0]
        self.effective_limit = min(limits) if limits else self.requested_size

        if self.requested_size > self.effective_limit:
            self.status = "RESIZED"
            self.approved_size = self.effective_limit
        else:
            self.approved_size = self.requested_size
            self.status = "APPROVED"

        return self.effective_limit
