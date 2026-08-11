"""
Backpressure Controller — flow control mechanism to prevent system
overload by throttling producers when consumers fall behind.

Commit 16 Part 1.4
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class BackpressureStrategy(str, Enum):
    BLOCK = "block"               # Block producer until space available
    DROP_OLDEST = "drop_oldest"   # Drop oldest events when full
    DROP_NEWEST = "drop_newest"   # Drop newest events when full
    THROTTLE = "throttle"         # Slow down producer rate


@dataclass
class BackpressureState:
    """Current backpressure state for a topic."""
    topic: str
    queue_size: int = 0
    queue_limit: int = 10000
    is_backpressured: bool = False
    strategy: BackpressureStrategy = BackpressureStrategy.BLOCK
    dropped_events: int = 0
    throttle_rate: float = 1.0  # 1.0 = full speed, 0.0 = stopped
    last_updated: float = field(default_factory=time.monotonic)


class BackpressureController:
    """
    Flow control to prevent system overload.

    Monitors queue depth per topic and applies backpressure
    strategies when consumers fall behind producers.

    Flow:
        Producer → Queue → Consumer → Throttle (if full)

    Usage::

        ctrl = BackpressureController()
        ctrl.set_limit("market.tick", 50000)
        allowed = await ctrl.try_accept("market.tick", event)
        state = ctrl.get_state("market.tick")
    """

    def __init__(self, default_queue_limit: int = 100000) -> None:
        self.default_queue_limit = default_queue_limit
        self._states: dict[str, BackpressureState] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self._total_dropped = 0

    def set_limit(self, topic: str, limit: int) -> None:
        """Set the queue size limit for a topic."""
        if topic not in self._states:
            self._states[topic] = BackpressureState(topic=topic)
        self._states[topic].queue_limit = limit

    def set_strategy(self, topic: str, strategy: BackpressureStrategy) -> None:
        """Set the backpressure strategy for a topic."""
        if topic not in self._states:
            self._states[topic] = BackpressureState(topic=topic)
        self._states[topic].strategy = strategy

    async def try_accept(self, topic: str, event: Any) -> bool:
        """Try to accept an event. Returns True if accepted."""
        if topic not in self._locks:
            self._locks[topic] = asyncio.Lock()

        state = self._states.get(topic)
        if state is None:
            state = BackpressureState(
                topic=topic,
                queue_limit=self.default_queue_limit,
            )
            self._states[topic] = state

        async with self._locks[topic]:
            if state.queue_size >= state.queue_limit:
                state.is_backpressured = True

                if state.strategy == BackpressureStrategy.BLOCK:
                    # Block until space is available (simulated here)
                    logger.warning("Backpressure BLOCK on %s (queue=%d/%d)",
                                   topic, state.queue_size, state.queue_limit)
                    return False

                elif state.strategy == BackpressureStrategy.DROP_OLDEST:
                    state.dropped_events += 1
                    self._total_dropped += 1
                    state.queue_size = state.queue_limit  # effectively drops oldest
                    return True

                elif state.strategy == BackpressureStrategy.DROP_NEWEST:
                    state.dropped_events += 1
                    self._total_dropped += 1
                    logger.debug("Backpressure DROP on %s", topic)
                    return False

                elif state.strategy == BackpressureStrategy.THROTTLE:
                    state.throttle_rate = max(0.1, state.throttle_rate * 0.5)
                    logger.debug("Throttling %s to %.2f", topic, state.throttle_rate)
                    return True

            state.queue_size += 1
            state.is_backpressured = False
            state.last_updated = time.monotonic()
            return True

    async def mark_consumed(self, topic: str, count: int = 1) -> None:
        """Mark events as consumed, freeing queue space."""
        state = self._states.get(topic)
        if state:
            state.queue_size = max(0, state.queue_size - count)
            if state.queue_size < state.queue_limit * 0.5:
                state.is_backpressured = False
                state.throttle_rate = min(1.0, state.throttle_rate * 1.2)

    def get_state(self, topic: str) -> Optional[BackpressureState]:
        """Get the current backpressure state for a topic."""
        return self._states.get(topic)

    async def stats(self) -> dict[str, Any]:
        """Get backpressure controller statistics."""
        total_dropped = sum(s.dropped_events for s in self._states.values())
        backpressured_topics = [
            topic for topic, s in self._states.items()
            if s.is_backpressured
        ]

        return {
            "topics_managed": len(self._states),
            "backpressured_topics": backpressured_topics,
            "total_dropped": total_dropped,
            "states": {
                topic: {
                    "queue_size": s.queue_size,
                    "queue_limit": s.queue_limit,
                    "is_backpressured": s.is_backpressured,
                    "strategy": s.strategy.value,
                    "dropped": s.dropped_events,
                    "throttle_rate": round(s.throttle_rate, 2),
                }
                for topic, s in self._states.items()
            },
        }
