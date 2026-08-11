"""
Signal Manager — Central coordinator for signal subsystems.

Part of Commit 13 Part 1.2: Signal & Alpha Engine.

Provides:
    - Event bus for inter-component communication
    - Subsystem lifecycle coordination
    - Cross-cutting configuration management
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Coroutine, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Event System
# ---------------------------------------------------------------------------

class ManagerEventType(str, Enum):
    """Signal manager event types."""
    # Signal lifecycle
    SIGNAL_GENERATED = "signal.generated"
    SIGNAL_VALIDATED = "signal.validated"
    SIGNAL_PUBLISHED = "signal.published"
    SIGNAL_CANCELLED = "signal.cancelled"
    SIGNAL_EXPIRED = "signal.expired"

    # Alpha lifecycle
    ALPHA_GENERATED = "alpha.generated"
    ALPHA_COMBINED = "alpha.combined"
    ALPHA_DECAYED = "alpha.decayed"

    # System
    SUBSYSTEM_INITIALIZED = "system.initialized"
    SUBSYSTEM_SHUTDOWN = "system.shutdown"
    ERROR_OCCURRED = "system.error"

    # Market
    MARKET_REGIME_CHANGED = "market.regime_changed"


@dataclass
class ManagerEvent:
    """An event in the signal manager event bus."""
    event_type: ManagerEventType
    source: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    payload: Dict[str, Any] = field(default_factory=dict)
    event_id: str = field(default_factory=lambda: str(int(datetime.now(timezone.utc).timestamp() * 1_000_000)))


EventHandler = Callable[[ManagerEvent], Coroutine[Any, Any, None]]


# ---------------------------------------------------------------------------
# Signal Manager
# ---------------------------------------------------------------------------

class SignalManager:
    """Central coordinator for all signal and alpha subsystems.

    Responsibilities:
        - Event bus for decoupled inter-component communication
        - Lifecycle orchestration of subsystems
        - Configuration management
        - Dependency injection hub
    """

    def __init__(self):
        self._initialized = False
        self._running = False

        # Event bus
        self._listeners: Dict[ManagerEventType, List[EventHandler]] = defaultdict(list)
        self._event_queue: asyncio.Queue = asyncio.Queue(maxsize=10000)
        self._event_task: Optional[asyncio.Task] = None

        # Subsystem references (set during wiring)
        self._subsystems: Dict[str, Any] = {}

        # Configuration
        self.config: Dict[str, Any] = {
            "max_active_signals": 5000,
            "signal_ttl_seconds": 300.0,
            "dispatch_batch_size": 100,
            "ranking_timeout_seconds": 5.0,
        }

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        if self._initialized:
            return
        self._running = True
        self._event_task = asyncio.create_task(self._event_loop())
        self._initialized = True
        logger.info("SignalManager initialized")

    async def shutdown(self) -> None:
        self._running = False
        if self._event_task:
            self._event_task.cancel()
            try:
                await self._event_task
            except asyncio.CancelledError:
                pass
        self._listeners.clear()
        self._initialized = False
        logger.info("SignalManager shut down")

    # ------------------------------------------------------------------
    # Event Bus
    # ------------------------------------------------------------------

    def subscribe(self, event_type: ManagerEventType, handler: EventHandler) -> None:
        """Register a handler for a specific event type."""
        self._listeners[event_type].append(handler)
        logger.debug("Subscribed to %s (total=%d)", event_type.value, len(self._listeners[event_type]))

    def unsubscribe(self, event_type: ManagerEventType, handler: EventHandler) -> None:
        """Remove a handler for a specific event type."""
        if handler in self._listeners[event_type]:
            self._listeners[event_type].remove(handler)

    async def emit(self, event: ManagerEvent) -> None:
        """Emit an event to all registered listeners asynchronously."""
        try:
            self._event_queue.put_nowait(event)
        except asyncio.QueueFull:
            logger.warning("Event queue full, dropping event: %s", event.event_type.value)

    async def emit_sync(self, event: ManagerEvent) -> None:
        """Emit an event and wait for all handlers to complete."""
        handlers = self._listeners.get(event.event_type, [])
        if not handlers:
            return
        tasks = [handler(event) for handler in handlers]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for result in results:
            if isinstance(result, Exception):
                logger.error("Event handler error for %s: %s", event.event_type.value, result)

    async def _event_loop(self) -> None:
        """Background task that processes the event queue."""
        while self._running:
            try:
                event = await asyncio.wait_for(self._event_queue.get(), timeout=1.0)
                handlers = self._listeners.get(event.event_type, [])
                for handler in handlers:
                    try:
                        await handler(event)
                    except Exception:
                        logger.exception(
                            "Error in handler for event %s", event.event_type.value,
                        )
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Event loop error")

    # ------------------------------------------------------------------
    # Subsystem Registry
    # ------------------------------------------------------------------

    def register_subsystem(self, name: str, instance: Any) -> None:
        """Register a subsystem for coordination."""
        self._subsystems[name] = instance
        logger.debug("Registered subsystem: %s", name)

    def get_subsystem(self, name: str) -> Optional[Any]:
        """Retrieve a registered subsystem."""
        return self._subsystems.get(name)

    def list_subsystems(self) -> List[str]:
        """List all registered subsystem names."""
        return list(self._subsystems.keys())

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def get_config(self, key: str, default: Any = None) -> Any:
        return self.config.get(key, default)

    def set_config(self, key: str, value: Any) -> None:
        self.config[key] = value

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    def listener_count(self, event_type: ManagerEventType) -> int:
        return len(self._listeners.get(event_type, []))
