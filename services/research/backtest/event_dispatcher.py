"""Event Dispatcher — routes backtest events to registered handlers.

Decouples event producers from consumers via a middleware pattern,
allowing dynamic handler registration and chaining.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Callable, Dict, List, Optional

from .event_queue import BacktestEvent

logger = logging.getLogger(__name__)


# Handler callback signature
EventHandler = Callable[[BacktestEvent], Any]


class EventDispatcher:
    """Routes backtest events to registered handlers.

    Features:
    * Typed handler registration per event type
    * Wildcard handler registration (matches all events)
    * Middleware pipeline support (pre/post processing)
    * Error isolation (one handler's error doesn't crash others)
    * Latency tracking per handler
    """

    def __init__(self, max_concurrent: int = 10) -> None:
        self._handlers: Dict[str, List[EventHandler]] = {}
        self._middlewares: List[EventHandler] = []
        self._wildcard_handlers: List[EventHandler] = []
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._dispatch_count: Dict[str, int] = {}
        self._error_count: Dict[str, int] = {}

    # ── registration ───────────────────────────────────────────────────────

    def register(self, event_type: str, handler: EventHandler) -> None:
        """Register a handler for a specific event type.

        Args:
            event_type: The type of event to handle.
            handler: Callable that accepts a BacktestEvent.
        """
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        if handler not in self._handlers[event_type]:
            self._handlers[event_type].append(handler)
            logger.debug("Registered handler '%s' for event type '%s'", handler.__name__, event_type)

    def register_wildcard(self, handler: EventHandler) -> None:
        """Register a handler that receives ALL event types."""
        if handler not in self._wildcard_handlers:
            self._wildcard_handlers.append(handler)

    def register_middleware(self, middleware: EventHandler) -> None:
        """Register a middleware that runs before/around handlers.

        Middlewares receive the event before typed handlers do.
        They can modify the event or short-circuit dispatch
        by returning a truthy value.
        """
        self._middlewares.append(middleware)

    def unregister(self, event_type: str, handler: Optional[EventHandler] = None) -> int:
        """Unregister handlers. If handler is None, removes all for that type."""
        if handler is None:
            removed = len(self._handlers.pop(event_type, []))
            return removed
        if event_type in self._handlers:
            before = len(self._handlers[event_type])
            self._handlers[event_type] = [h for h in self._handlers[event_type] if h != handler]
            return before - len(self._handlers[event_type])
        return 0

    # ── dispatch ───────────────────────────────────────────────────────────

    async def dispatch(self, event: BacktestEvent) -> Dict[str, Any]:
        """Dispatch an event to all registered handlers.

        Dispatch order:
        1. Wildcard handlers (receive all events)
        2. Typed handlers matching event.event_type

        Args:
            event: The backtest event to dispatch.

        Returns:
            Dictionary with dispatch stats.
        """
        dispatch_id = f"{event.event_id[:8]}"
        start_time = time.monotonic()

        # Track dispatch count
        self._dispatch_count[event.event_type] = self._dispatch_count.get(event.event_type, 0) + 1

        # Run middlewares
        for mw in self._middlewares:
            try:
                result = await self._run_handler(mw, event)
                if result:  # middleware short-circuits
                    logger.debug("Middleware '%s' short-circuited dispatch", mw.__name__)
                    return {"dispatched": False, "short_circuit": True, "event_type": event.event_type}
            except Exception:
                logger.exception("Middleware '%s' error", mw.__name__)

        # Dispatch to wildcard handlers
        for handler in self._wildcard_handlers:
            await self._safe_dispatch(handler, event)

        # Dispatch to typed handlers
        handlers = self._handlers.get(event.event_type, [])
        for handler in handlers:
            await self._safe_dispatch(handler, event)

        elapsed_ms = (time.monotonic() - start_time) * 1000
        return {
            "dispatched": True,
            "event_type": event.event_type,
            "event_id": dispatch_id,
            "handler_count": len(handlers) + len(self._wildcard_handlers),
            "elapsed_ms": elapsed_ms,
        }

    async def dispatch_batch(self, events: List[BacktestEvent]) -> List[Dict[str, Any]]:
        """Dispatch multiple events concurrently."""
        tasks = [self.dispatch(event) for event in events]
        return await asyncio.gather(*tasks, return_exceptions=True)

    # ── internals ──────────────────────────────────────────────────────────

    async def _safe_dispatch(self, handler: EventHandler, event: BacktestEvent) -> None:
        """Dispatch to a single handler with error isolation."""
        async with self._semaphore:
            try:
                start = time.monotonic()
                await self._run_handler(handler, event)
                elapsed = (time.monotonic() - start) * 1000
                if elapsed > 100:
                    logger.warning(
                        "Slow handler '%s': %.1fms for event %s",
                        handler.__name__, elapsed, event.event_type,
                    )
            except Exception:
                self._error_count[handler.__name__] = self._error_count.get(handler.__name__, 0) + 1
                logger.exception("Handler '%s' error processing event %s", handler.__name__, event.event_type)

    async def _run_handler(self, handler: EventHandler, event: BacktestEvent) -> Any:
        """Run a handler, supporting both sync and async callables."""
        result = handler(event)
        if asyncio.iscoroutine(result):
            return await result
        return result

    # ── query ──────────────────────────────────────────────────────────────

    def get_registered_types(self) -> List[str]:
        """List all registered event types."""
        return sorted(self._handlers.keys())

    def get_handler_count(self, event_type: Optional[str] = None) -> int:
        """Get the number of registered handlers."""
        if event_type:
            return len(self._handlers.get(event_type, []))
        return sum(len(v) for v in self._handlers.values()) + len(self._wildcard_handlers)

    def get_stats(self) -> Dict[str, Any]:
        """Return dispatcher statistics."""
        return {
            "registered_types": len(self._handlers),
            "total_handlers": sum(len(v) for v in self._handlers.values()),
            "wildcard_handlers": len(self._wildcard_handlers),
            "middlewares": len(self._middlewares),
            "dispatch_counts": dict(self._dispatch_count),
            "error_counts": dict(self._error_count),
        }
