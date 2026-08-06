"""Event Engine — orchestration layer for event-driven backtesting.

Coordinates the event queue and dispatcher, providing the central
nervous system for the event-driven backtesting architecture.

Event Flow::

    Replay → EventQueue → EventDispatcher → StrategyRuntime → Order → Trade
"""

from __future__ import annotations

import asyncio
import logging
import time
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from .event_queue import EventQueue, BacktestEvent, EventPriority
from .event_dispatcher import EventDispatcher

logger = logging.getLogger(__name__)


class BacktestEventType(str, Enum):
    """Standard backtest event types."""

    # Market events
    MARKET = "market"
    BAR = "bar"
    TICK = "tick"
    QUOTE = "quote"

    # Signal events
    SIGNAL = "signal"

    # Order events
    ORDER = "order"
    ORDER_UPDATE = "order_update"
    ORDER_CANCEL = "order_cancel"

    # Execution events
    TRADE = "trade"
    FILL = "fill"
    REJECTION = "rejection"

    # Position events
    POSITION = "position"
    POSITION_UPDATE = "position_update"

    # Settlement events
    SETTLEMENT = "settlement"
    EOD = "eod"  # end of day

    # Corporate action events
    CORPORATE_ACTION = "corporate_action"
    DIVIDEND = "dividend"
    SPLIT = "split"

    # System events
    TIMER = "timer"
    HEARTBEAT = "heartbeat"
    SHUTDOWN = "shutdown"
    ERROR = "error"


class EventEngine:
    """Orchestrates event queue and dispatcher for backtesting.

    Provides:
    * Central event production (push to queue)
    * Central event consumption (dispatch via registered handlers)
    * Event lifecycle callbacks
    * Queue monitoring and drain
    """

    def __init__(self) -> None:
        self._queue = EventQueue()
        self._dispatcher = EventDispatcher()
        self._handlers: Dict[str, Callable] = {}
        self._on_event: Optional[Callable] = None
        self._running = False
        self._events_processed = 0
        self._events_error = 0

    # ── event production ───────────────────────────────────────────────────

    def push(self, event: BacktestEvent) -> None:
        """Synchronously push an event (runs in the current event loop).

        Use this for immediate dispatch within the same event-loop tick.
        """
        self._queue._heap.append(event)  # Bypass async for sync dispatch
        # Actually, let's use the proper async method synchronously
        # Schedule on the running loop
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._queue.push(event))
        except RuntimeError:
            # No running loop, store directly
            asyncio.run(self._queue.push(event))

    async def push_async(self, event: BacktestEvent) -> bool:
        """Asynchronously push an event to the queue."""
        return await self._queue.push(event)

    async def push_market_event(
        self,
        timestamp: str,
        data: Dict[str, Any],
        symbol: Optional[str] = None,
    ) -> None:
        """Convenience method: push a market data event."""
        event = BacktestEvent(
            event_type=BacktestEventType.MARKET.value,
            timestamp=timestamp,
            data=data,
            metadata={"symbol": symbol} if symbol else {},
            priority=EventPriority.MEDIUM,
        )
        await self._queue.push(event)

    async def push_signal_event(
        self, timestamp: str, signal: Dict[str, Any]
    ) -> None:
        """Convenience method: push a trading signal event."""
        event = BacktestEvent(
            event_type=BacktestEventType.SIGNAL.value,
            timestamp=timestamp,
            data=signal,
            priority=EventPriority.HIGH,
        )
        await self._queue.push(event)

    # ── event consumption ──────────────────────────────────────────────────

    async def dispatch(self, callback: Optional[Callable] = None) -> int:
        """Dispatch all pending events in the queue.

        Args:
            callback: Optional global callback invoked for every dispatched event.

        Returns:
            Number of events dispatched.
        """
        count = 0
        while True:
            event = await self._queue.pop()
            if event is None:
                break

            try:
                result = await self._dispatcher.dispatch(event)
                if callback:
                    cb_result = callback(event)
                    if asyncio.iscoroutine(cb_result):
                        await cb_result

                count += 1
                self._events_processed += 1

            except Exception:
                self._events_error += 1
                logger.exception("Failed to dispatch event: %s", event.event_id[:8])

        return count

    async def dispatch_all(self) -> int:
        """Dispatch all events until queue is empty."""
        return await self.dispatch()

    # ── handler registration ───────────────────────────────────────────────

    def register_handler(
        self,
        event_type: BacktestEventType,
        handler: Callable,
    ) -> None:
        """Register a handler for a specific event type.

        Args:
            event_type: The BacktestEventType to handle.
            handler: Async or sync callable that accepts a BacktestEvent.
        """
        self._dispatcher.register(event_type.value, handler)
        self._handlers[event_type.value] = handler

    def register_global_handler(self, handler: Callable) -> None:
        """Register a handler for ALL event types."""
        self._dispatcher.register_wildcard(handler)

    def set_event_callback(self, callback: Callable) -> None:
        """Set a callback invoked after every dispatched event."""
        self._on_event = callback

    # ── lifecycle ──────────────────────────────────────────────────────────

    async def start(self) -> None:
        """Start the event engine."""
        self._running = True
        logger.info("Event Engine started")

    async def stop(self) -> None:
        """Stop the event engine."""
        self._running = False
        logger.info("Event Engine stopped")

    async def drain(self) -> int:
        """Drain all remaining events from the queue."""
        count = await self._queue.size()
        await self.dispatch_all()
        logger.info("Event Engine drained %d events", count)
        return count

    # ── query ──────────────────────────────────────────────────────────────

    async def queue_size(self) -> int:
        """Get current event queue size."""
        return await self._queue.size()

    async def get_stats(self) -> Dict[str, Any]:
        """Return engine statistics."""
        return {
            "queue": await self._queue.stats(),
            "dispatcher": self._dispatcher.get_stats(),
            "events_processed": self._events_processed,
            "events_error": self._events_error,
            "running": self._running,
        }

    def get_dispatcher(self) -> EventDispatcher:
        """Get the event dispatcher for direct handler registration."""
        return self._dispatcher
