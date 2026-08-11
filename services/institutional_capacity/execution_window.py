"""
Execution Window — Time-based capacity modeling for order execution.

Same 10M order: 5 minutes → high pressure, 2 hours → much lower pressure.
Models capacity as a function of available execution time.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class WindowType(str, Enum):
    IMMEDIATE = "immediate"           # < 1 minute
    URGENT = "urgent"                 # 1-15 minutes
    STANDARD = "standard"             # 15-60 minutes
    PATIENT = "patient"               # 1-4 hours
    DAY = "day"                       # full day
    MULTI_DAY = "multi_day"           # > 1 day


WINDOW_MINUTES: Dict[WindowType, float] = {
    WindowType.IMMEDIATE: 1,
    WindowType.URGENT: 15,
    WindowType.STANDARD: 60,
    WindowType.PATIENT: 240,
    WindowType.DAY: 390,              # 6.5 hour trading day
    WindowType.MULTI_DAY: 1560,       # ~4 days
}


@dataclass
class ExecutionWindow:
    """Execution time window capacity model."""

    window_id: str = field(default_factory=lambda: f"EW-{uuid.uuid4().hex[:8]}")
    window_type: WindowType = WindowType.STANDARD
    window_minutes: float = 60.0

    # Capacity model
    total_volume_in_window: float = 0.0
    max_participation: float = 0.10
    max_executable: float = 0.0

    # For split execution
    slices: int = 1
    per_slice_capacity: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "window_id": self.window_id,
            "window_type": self.window_type.value,
            "window_minutes": self.window_minutes,
            "max_executable": self.max_executable,
            "slices": self.slices,
        }

    def compute_capacity(self, avg_minute_volume: float) -> float:
        """Compute maximum executable in this window."""
        self.total_volume_in_window = avg_minute_volume * self.window_minutes
        self.max_executable = self.total_volume_in_window * self.max_participation
        return self.max_executable

    def optimal_slices(self, order_size: float, avg_minute_volume: float) -> int:
        """Compute optimal number of slices for an order."""
        per_minute_capacity = avg_minute_volume * self.max_participation
        if per_minute_capacity <= 0:
            return 1
        return max(1, int(order_size / per_minute_capacity) + 1)

    @classmethod
    def from_window_type(cls, window_type: WindowType, max_participation: float = 0.10) -> "ExecutionWindow":
        return cls(
            window_type=window_type,
            window_minutes=WINDOW_MINUTES.get(window_type, 60),
            max_participation=max_participation,
        )
