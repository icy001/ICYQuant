"""Execution Plan – structured execution schedule for a single order."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional


@dataclass
class Slice:
    """A single slice within an execution plan."""

    slice_id: int
    quantity: int
    strategy: str  # "market", "limit", "VWAP", "TWAP", "POV"
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    venue: str = "auto"

    def to_dict(self) -> dict:
        return {
            "slice_id": self.slice_id,
            "quantity": self.quantity,
            "strategy": self.strategy,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "venue": self.venue,
        }


@dataclass
class ExecutionPlan:
    """A complete execution plan for an order.

    Contains the primary strategy, slicing schedule, estimated costs,
    and execution constraints derived from market conditions.
    """

    order_id: str = ""
    symbol: str = ""
    side: str = ""

    # Strategy
    strategy: str = "VWAP"  # primary strategy: "VWAP", "TWAP", "POV", "adaptive"
    duration: int = 300  # total execution duration in seconds
    urgency: str = "normal"

    # Slices
    slices: List[Slice] = field(default_factory=list)
    total_quantity: int = 0

    # Cost estimates
    estimated_slippage_bps: float = 0.0
    estimated_impact_bps: float = 0.0
    estimated_cost_bps: float = 0.0

    # Constraints
    max_participation_rate: float = 0.10  # max % of market volume
    min_fill_rate: float = 0.90  # target minimum fill rate

    def add_slice(self, quantity: int, strategy: str = "VWAP",
                  venue: str = "auto") -> Slice:
        """Append a new slice to the plan."""
        s = Slice(
            slice_id=len(self.slices) + 1,
            quantity=quantity,
            strategy=strategy,
            venue=venue,
        )
        self.slices.append(s)
        self.total_quantity += quantity
        return s

    def remaining_quantity(self, filled: int) -> int:
        """Compute unfilled quantity."""
        return max(self.total_quantity - filled, 0)

    def is_complete(self, filled: int) -> bool:
        return self.remaining_quantity(filled) <= 0

    def to_dict(self) -> dict:
        return {
            "order_id": self.order_id,
            "symbol": self.symbol,
            "side": self.side,
            "strategy": self.strategy,
            "duration": self.duration,
            "urgency": self.urgency,
            "slices": [s.to_dict() for s in self.slices],
            "total_quantity": self.total_quantity,
            "estimated_slippage_bps": self.estimated_slippage_bps,
            "estimated_impact_bps": self.estimated_impact_bps,
            "estimated_cost_bps": self.estimated_cost_bps,
            "max_participation_rate": self.max_participation_rate,
            "min_fill_rate": self.min_fill_rate,
        }
