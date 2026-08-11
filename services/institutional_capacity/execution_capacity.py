"""
Execution Capacity — How much can be executed given time, liquidity, and constraints.

Models the relationship: Order Size + Liquidity + Participation + Time → Executable.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ExecutionCapacity:
    """Capacity assessment for execution of a specific order."""

    capacity_id: str = field(default_factory=lambda: f"EC-{uuid.uuid4().hex[:8]}")
    strategy_id: str = ""
    asset: str = ""

    # Limits
    max_order_size: float = 0.0
    max_daily_execution: float = 0.0
    max_instantaneous: float = 0.0          # single aggressive fill

    # Time-based
    execution_window_minutes: float = 0.0
    orders_per_window: int = 0

    # Current
    executed_today: float = 0.0
    remaining: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "capacity_id": self.capacity_id,
            "strategy_id": self.strategy_id,
            "asset": self.asset,
            "max_order_size": self.max_order_size,
            "max_daily_execution": self.max_daily_execution,
            "executed_today": self.executed_today,
            "remaining": self.remaining,
        }

    def can_execute(self, size: float) -> bool:
        if self.remaining <= 0:
            return False
        if size > self.max_instantaneous:
            return False
        return size <= self.remaining

    def consume(self, size: float) -> bool:
        if self.can_execute(size):
            self.executed_today += size
            self.remaining = self.max_daily_execution - self.executed_today
            return True
        return False
