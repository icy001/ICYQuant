"""
Sliding Window — overlapping windows with fixed size and slide interval
for continuous stream aggregation.

Commit 16 Part 1.4
"""

from __future__ import annotations

import logging
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


class SlidingWindow:
    """
    Overlapping windows with fixed size and slide interval.

    Each event may belong to multiple windows. Windows slide forward
    by the slide interval, producing continuous aggregation results.

    Usage::

        window = SlidingWindow(size_ms=60000, slide_ms=10000)  # 1min windows, 10s slide
        window.add_event(event_time, {"price": 100, "volume": 50})
        results = window.get_ready_windows(current_watermark)
    """

    def __init__(
        self,
        size_ms: int,
        slide_ms: int,
        *,
        aggregator: Optional[Callable[[list[Any]], Any]] = None,
        max_late_ms: int = 0,
    ) -> None:
        if slide_ms > size_ms:
            raise ValueError("Slide interval cannot exceed window size")
        self.size_ms = size_ms
        self.slide_ms = slide_ms
        self.aggregator = aggregator
        self.max_late_ms = max_late_ms
        self._events: list[tuple[float, Any]] = []
        self._emitted: set[int] = set()

    def _window_id(self, timestamp_ms: float) -> int:
        """Get the earliest window ID containing this timestamp."""
        return int(timestamp_ms // self.slide_ms) - int(self.size_ms // self.slide_ms) + 1

    def _window_bounds(self, window_id: int) -> tuple[float, float]:
        """Get start/end timestamps for a window."""
        start = window_id * self.slide_ms
        end = start + self.size_ms
        return start, end

    def _get_windows_for_event(self, event_time_ms: float) -> list[int]:
        """Get all window IDs that contain this event."""
        # Find the range of windows that overlap this event time
        latest_window = int(event_time_ms // self.slide_ms)
        earliest_window = latest_window - int(self.size_ms // self.slide_ms) + 1
        return list(range(earliest_window, latest_window + 1))

    def add_event(self, event_time_ms: float, event: Any) -> None:
        """Add an event to all overlapping windows."""
        self._events.append((event_time_ms, event))

        # Prune old events
        cutoff = event_time_ms - self.size_ms - self.max_late_ms
        self._events = [(t, e) for t, e in self._events if t >= cutoff]

    def get_ready_windows(self, watermark_ms: float) -> list[WindowResult]:
        """Get windows that are ready for emission."""
        results = []
        latest_window = int(watermark_ms // self.slide_ms)

        # Emit windows that are fully past the watermark
        for window_id in range(latest_window - int(self.size_ms // self.slide_ms), latest_window):
            if window_id in self._emitted:
                continue

            start, end = self._window_bounds(window_id)
            if watermark_ms >= end + self.max_late_ms:
                self._emitted.add(window_id)
                window_events = [
                    e for t, e in self._events
                    if start <= t < end
                ]
                result = self._compute(window_id, window_events)
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
        """Clear old events to free memory."""
        self._emitted.clear()
        return 0

    @property
    def event_count(self) -> int:
        return len(self._events)
