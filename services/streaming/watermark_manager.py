"""
Watermark Manager — event-time watermark tracking for handling
out-of-order events and late arrivals in stream processing.

Commit 16 Part 1.4
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class LateEventPolicy(str, Enum):
    DROP = "drop"               # Discard late events
    SIDE_OUTPUT = "side_output" # Emit to side output
    UPDATE = "update"           # Update previously emitted results
    ACCEPT = "accept"           # Accept and process normally


@dataclass
class Watermark:
    """A watermark for a specific stream/topic."""
    topic: str
    watermark_ms: float
    last_event_time_ms: float = 0.0
    max_out_of_orderness_ms: int = 5000
    updated_at: float = field(default_factory=time.monotonic)


class WatermarkManager:
    """
    Tracks event-time watermarks across streams.

    Handles out-of-order events, late arrivals, and provides
    watermark-based window triggering.

    Flow:
        Event Time → Watermark → Late Event Detection → Policy

    Usage::

        mgr = WatermarkManager(max_out_of_orderness_ms=5000)
        mgr.update_watermark("market.tick", event_time_ms)
        watermark = mgr.get_watermark("market.tick")
        is_late = mgr.is_late("market.tick", event_time_ms)
    """

    def __init__(
        self,
        max_out_of_orderness_ms: int = 5000,
        late_policy: LateEventPolicy = LateEventPolicy.SIDE_OUTPUT,
    ) -> None:
        self.max_out_of_orderness_ms = max_out_of_orderness_ms
        self.late_policy = late_policy
        self._watermarks: dict[str, Watermark] = {}
        self._late_events: dict[str, list[Any]] = {}
        self._total_late_events = 0
        self._total_events = 0

    def update_watermark(self, topic: str, event_time_ms: float) -> float:
        """Update the watermark for a topic with a new event time."""
        self._total_events += 1

        if topic not in self._watermarks:
            self._watermarks[topic] = Watermark(
                topic=topic,
                watermark_ms=event_time_ms - self.max_out_of_orderness_ms,
                last_event_time_ms=event_time_ms,
                max_out_of_orderness_ms=self.max_out_of_orderness_ms,
            )

        wm = self._watermarks[topic]
        wm.last_event_time_ms = max(wm.last_event_time_ms, event_time_ms)
        wm.watermark_ms = max(
            wm.watermark_ms,
            event_time_ms - self.max_out_of_orderness_ms,
        )
        wm.updated_at = time.monotonic()
        return wm.watermark_ms

    def get_watermark(self, topic: str) -> float:
        """Get the current watermark for a topic."""
        wm = self._watermarks.get(topic)
        return wm.watermark_ms if wm else 0.0

    def is_late(self, topic: str, event_time_ms: float) -> bool:
        """Check if an event is late relative to the watermark."""
        watermark = self.get_watermark(topic)
        return event_time_ms < watermark

    def handle_late_event(self, topic: str, event_time_ms: float, event: Any) -> Any:
        """Handle a late event according to the configured policy."""
        if not self.is_late(topic, event_time_ms):
            return event

        self._total_late_events += 1

        if self.late_policy == LateEventPolicy.DROP:
            logger.debug("Dropping late event for %s (time=%d, watermark=%d)",
                         topic, event_time_ms, self.get_watermark(topic))
            return None

        elif self.late_policy == LateEventPolicy.SIDE_OUTPUT:
            if topic not in self._late_events:
                self._late_events[topic] = []
            self._late_events[topic].append(event)
            return None

        elif self.late_policy == LateEventPolicy.ACCEPT:
            return event

        elif self.late_policy == LateEventPolicy.UPDATE:
            # Accept but flag as late for downstream correction
            if isinstance(event, dict):
                event["_late"] = True
            return event

        return event

    def get_late_events(self, topic: str) -> list[Any]:
        """Get accumulated late events for a topic."""
        return self._late_events.get(topic, [])

    def clear_late_events(self, topic: str) -> int:
        """Clear accumulated late events for a topic."""
        count = len(self._late_events.get(topic, []))
        self._late_events.pop(topic, None)
        return count

    async def stats(self) -> dict[str, Any]:
        """Get watermark manager statistics."""
        return {
            "topics": len(self._watermarks),
            "total_events": self._total_events,
            "total_late_events": self._total_late_events,
            "late_rate": (
                self._total_late_events / max(self._total_events, 1)
            ),
            "late_policy": self.late_policy.value,
            "watermarks": {
                topic: {
                    "watermark_ms": wm.watermark_ms,
                    "last_event_ms": wm.last_event_time_ms,
                }
                for topic, wm in self._watermarks.items()
            },
        }
