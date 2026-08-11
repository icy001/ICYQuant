"""
Tumbling Window — fixed-size, non-overlapping windows for stream
aggregation with strict boundaries.

Commit 16 Part 1.4
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


@dataclass
class WindowResult:
    """Result of a window computation."""
    window_start: float
    window_end: float
    event_count: int
    result: Any
    metadata: dict[str, Any] = field(default_factory=dict)


class TumblingWindow:
    """
    Fixed-size, non-overlapping windows.

    Each event belongs to exactly one window. Windows are triggered
    when the window boundary is crossed.

    Usage::

        window = TumblingWindow(size_ms=60000)  # 1 minute windows
        window.add_event(event_time, {"price": 100, "volume": 50})
        results = window.get_ready_windows(current_watermark)
    """

    def __init__(
        self,
        size_ms: int,
        *,
        aggregator: Optional[Callable[[list[Any]], Any]] = None,
        max_late_ms: int = 0,
    ) -> None:
        self.size_ms = size_ms
        self.aggregator = aggregator
        self.max_late_ms = max_late_ms
        self._windows: dict[int, list[Any]] = {}
        self._emitted: set[int] = set()

    def _window_id(self, timestamp_ms: float) -> int:
        """Get the window ID for a timestamp."""
        return int(timestamp_ms // self.size_ms)

    def _window_bounds(self, window_id: int) -> tuple[float, float]:
        """Get the start and end timestamps for a window."""
        start = window_id * self.size_ms
        end = start + self.size_ms
        return start, end

    def add_event(self, event_time_ms: float, event: Any) -> None:
        """Add an event to its corresponding window."""
        window_id = self._window_id(event_time_ms)
        if window_id not in self._windows:
            self._windows[window_id] = []
        self._windows[window_id].append(event)

    def get_ready_windows(self, watermark_ms: float) -> list[WindowResult]:
        """Get windows that are ready for emission (watermark has passed window end)."""
        results = []
        for window_id, events in list(self._windows.items()):
            _, window_end = self._window_bounds(window_id)
            if watermark_ms >= window_end + self.max_late_ms:
                if window_id not in self._emitted:
                    self._emitted.add(window_id)
                    result = self._compute(window_id, events)
                    results.append(result)
        return results

    def _compute(self, window_id: int, events: list[Any]) -> WindowResult:
        """Compute the result for a window."""
        start, end = self._window_bounds(window_id)
        if self.aggregator:
            agg_result = self.aggregator(events)
        else:
            agg_result = events

        return WindowResult(
            window_start=start,
            window_end=end,
            event_count=len(events),
            result=agg_result,
        )

    async def clear_emitted(self) -> int:
        """Clear emitted windows to free memory."""
        count = 0
        for window_id in self._emitted:
            if window_id in self._windows:
                del self._windows[window_id]
                count += 1
        self._emitted.clear()
        return count

    @property
    def active_window_count(self) -> int:
        return len(self._windows)

    @property
    def total_events(self) -> int:
        return sum(len(e) for e in self._windows.values())
