"""
Global Window — a single unbounded window that accumulates all events
for the lifetime of the stream, triggered only by custom triggers.

Commit 16 Part 1.4
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class TriggerType(str, Enum):
    COUNT = "count"         # Trigger after N events
    TIME = "time"           # Trigger every N milliseconds
    WATERMARK = "watermark" # Trigger on watermark advancement
    CUSTOM = "custom"       # Trigger via custom predicate


@dataclass
class WindowResult:
    """Result of a window computation."""
    window_start: float
    window_end: float
    event_count: int
    result: Any
    metadata: dict[str, Any] = field(default_factory=dict)


class GlobalWindow:
    """
    A single unbounded window accumulating all events.

    Unlike tumbling/sliding windows, the global window never closes
    automatically. Results are emitted only via triggers.

    Usage::

        window = GlobalWindow(
            trigger_type=TriggerType.COUNT,
            trigger_value=1000,  # emit every 1000 events
        )
        window.add_event(event)
        results = window.check_trigger()
    """

    def __init__(
        self,
        *,
        trigger_type: TriggerType = TriggerType.COUNT,
        trigger_value: int = 10000,
        aggregator: Optional[Callable[[list[Any]], Any]] = None,
        custom_trigger: Optional[Callable[[list[Any], int], bool]] = None,
        evict_after_trigger: bool = False,
    ) -> None:
        self.trigger_type = trigger_type
        self.trigger_value = trigger_value
        self.aggregator = aggregator
        self.custom_trigger = custom_trigger
        self.evict_after_trigger = evict_after_trigger

        self._events: list[Any] = []
        self._start_time: float = 0.0
        self._last_trigger_time: float = 0.0
        self._trigger_count = 0

    def add_event(self, event_time_ms: float, event: Any) -> None:
        """Add an event to the global window."""
        if self._start_time == 0:
            self._start_time = event_time_ms
        self._events.append(event)

    def check_trigger(self, current_time_ms: Optional[float] = None) -> list[WindowResult]:
        """Check if the trigger condition is met and emit results."""
        should_trigger = False

        if self.trigger_type == TriggerType.COUNT:
            should_trigger = len(self._events) >= self.trigger_value
        elif self.trigger_type == TriggerType.TIME:
            if current_time_ms and self._last_trigger_time > 0:
                should_trigger = (
                    current_time_ms - self._last_trigger_time
                ) >= self.trigger_value
            elif self._last_trigger_time == 0 and current_time_ms:
                should_trigger = (
                    current_time_ms - self._start_time
                ) >= self.trigger_value
        elif self.trigger_type == TriggerType.CUSTOM:
            if self.custom_trigger:
                should_trigger = self.custom_trigger(self._events, self._trigger_count)

        if not should_trigger:
            return []

        result = self._compute()
        self._trigger_count += 1
        self._last_trigger_time = current_time_ms or 0

        if self.evict_after_trigger:
            self._events.clear()

        return [result]

    def _compute(self) -> WindowResult:
        """Compute the current result."""
        if self.aggregator:
            agg_result = self.aggregator(self._events)
        else:
            agg_result = self._events

        return WindowResult(
            window_start=self._start_time,
            window_end=0,  # unbounded
            event_count=len(self._events),
            result=agg_result,
            metadata={"trigger_count": self._trigger_count},
        )

    def force_emit(self) -> WindowResult:
        """Force emit the current accumulated result."""
        return self._compute()

    def clear(self) -> None:
        """Clear all accumulated events."""
        self._events.clear()
        self._start_time = 0
        self._last_trigger_time = 0
        self._trigger_count = 0

    @property
    def event_count(self) -> int:
        return len(self._events)

    @property
    def trigger_count(self) -> int:
        return self._trigger_count
