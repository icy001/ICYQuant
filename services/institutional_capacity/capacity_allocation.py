"""
Capacity Allocation — Allocates limited market capacity among competing strategies.

When multiple strategies target the same asset, market capacity must be
divided based on alpha, risk, priority, and efficiency.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class CapacityRequest:
    """A request for market capacity from a strategy."""

    request_id: str = field(default_factory=lambda: f"CR-{uuid.uuid4().hex[:8]}")
    strategy_id: str = ""
    asset: str = ""
    requested_amount: float = 0.0
    priority_score: float = 0.0
    expected_alpha: float = 0.0
    capital_efficiency: float = 0.0


@dataclass
class CapacityAllocation:
    """Result of allocating market capacity."""

    allocation_id: str = field(default_factory=lambda: f"CA-{uuid.uuid4().hex[:8]}")
    asset: str = ""
    total_capacity: float = 0.0
    total_requested: float = 0.0
    total_allocated: float = 0.0

    allocations: Dict[str, float] = field(default_factory=dict)  # strategy_id -> amount
    rejected: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "allocation_id": self.allocation_id,
            "asset": self.asset,
            "total_capacity": self.total_capacity,
            "total_requested": self.total_requested,
            "total_allocated": self.total_allocated,
            "allocated_strategies": len(self.allocations),
            "rejected": self.rejected,
        }
