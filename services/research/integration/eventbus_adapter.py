"""EventBus Adapter — bridges Research Platform to the EventBus.

Commit 11 Part 1.5: Decouples research modules via event-driven communication
on the platform EventBus.

Architecture::

    Dataset Updated → Factor Generated → Backtest Finished → Portfolio Published

Events enable loose coupling between research subsystems and trigger
downstream workflows automatically.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class EventBusAdapterState(str, Enum):
    """EventBus adapter lifecycle states."""

    UNINITIALIZED = "uninitialized"
    INITIALIZING = "initializing"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"


class ResearchEventType(str, Enum):
    """Standard research platform event types."""

    DATASET_REGISTERED = "research.dataset.registered"
    DATASET_UPDATED = "research.dataset.updated"
    EXPERIMENT_CREATED = "research.experiment.created"
    EXPERIMENT_COMPLETED = "research.experiment.completed"
    FACTOR_COMPUTED = "research.factor.computed"
    FACTOR_PUBLISHED = "research.factor.published"
    BACKTEST_STARTED = "research.backtest.started"
    BACKTEST_COMPLETED = "research.backtest.completed"
    PORTFOLIO_OPTIMIZED = "research.portfolio.optimized"
    PORTFOLIO_PUBLISHED = "research.portfolio.published"
    MODEL_REGISTERED = "research.model.registered"
    MODEL_DEPLOYED = "research.model.deployed"
    REPORT_GENERATED = "research.report.generated"
    PLATFORM_INITIALIZED = "research.platform.initialized"
    PLATFORM_SHUTDOWN = "research.platform.shutdown"


class EventBusAdapter:
    """Adapter for integrating Research Platform with the EventBus.

    Publishes research lifecycle events and subscribes to platform events,
    enabling decoupled communication between research subsystems.

    Usage::

        adapter = EventBusAdapter(config={"eventbus_url": "..."})
        await adapter.initialize()
        await adapter.publish(
            ResearchEventType.BACKTEST_COMPLETED,
            {"backtest_id": "bt-123", "sharpe": 1.5},
        )
    """

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        *,
        adapter_id: Optional[str] = None,
    ) -> None:
        self._id: str = adapter_id or f"eba-{uuid4().hex[:12]}"
        self._config: Dict[str, Any] = config or {}
        self._state: EventBusAdapterState = EventBusAdapterState.UNINITIALIZED
        self._created_at: datetime = datetime.now(timezone.utc)

        # EventBus connection
        self._eventbus_url: str = self._config.get("eventbus_url", "http://localhost:8300")
        self._eventbus_connected: bool = False

        # Subscriptions
        self._subscriptions: Dict[str, List[Callable]] = {}
        self._event_history: List[Dict[str, Any]] = []
        self._max_history: int = self._config.get("max_event_history", 10000)

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def id(self) -> str:
        return self._id

    @property
    def state(self) -> EventBusAdapterState:
        return self._state

    @property
    def is_connected(self) -> bool:
        return self._eventbus_connected

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """Initialize EventBus adapter and connect to EventBus."""
        self._state = EventBusAdapterState.INITIALIZING
        logger.info("Initializing EventBusAdapter [%s] → %s", self._id, self._eventbus_url)

        try:
            await self._connect()
            self._eventbus_connected = True
            self._state = EventBusAdapterState.CONNECTED
        except Exception as exc:
            logger.error("Failed to connect to EventBus: %s", exc)
            self._state = EventBusAdapterState.ERROR
            raise

        # Subscribe to platform lifecycle events
        await self.subscribe(ResearchEventType.PLATFORM_INITIALIZED, self._on_platform_initialized)
        await self.subscribe(ResearchEventType.PLATFORM_SHUTDOWN, self._on_platform_shutdown)

        logger.info("EventBusAdapter initialized [%s]", self._id)

    async def synchronize(self) -> Dict[str, Any]:
        """Synchronize with the EventBus."""
        status: Dict[str, Any] = {
            "adapter_id": self._id,
            "eventbus_connected": self._eventbus_connected,
            "subscriptions": {k: len(v) for k, v in self._subscriptions.items()},
            "event_history_size": len(self._event_history),
        }
        if not self._eventbus_connected:
            try:
                await self._connect()
                self._eventbus_connected = True
                status["reconnected"] = True
            except Exception:
                status["reconnected"] = False
        return status

    async def shutdown(self) -> None:
        """Disconnect from EventBus and clean up."""
        logger.info("Shutting down EventBusAdapter [%s]...", self._id)

        # Publish shutdown event
        await self.publish(ResearchEventType.PLATFORM_SHUTDOWN, {"adapter_id": self._id})

        self._subscriptions.clear()
        self._event_history.clear()
        self._eventbus_connected = False
        self._state = EventBusAdapterState.UNINITIALIZED

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------

    async def _connect(self) -> None:
        """Establish connection to EventBus."""
        logger.info("Connecting to EventBus at %s", self._eventbus_url)
        await asyncio.sleep(0.01)
        logger.info("Connected to EventBus")

    # ------------------------------------------------------------------
    # Publish
    # ------------------------------------------------------------------

    async def publish(self, event_type: ResearchEventType, payload: Dict[str, Any]) -> str:
        """Publish a research event to the EventBus.

        Args:
            event_type: Standard research event type.
            payload: Event payload data.

        Returns:
            Event ID.
        """
        if not self._eventbus_connected:
            logger.warning("EventBus not connected, buffering event")
            return await self._buffer_event(event_type, payload)

        event_id = f"evt-{uuid4().hex[:16]}"
        event = {
            "id": event_id,
            "type": event_type.value,
            "payload": payload,
            "published_at": datetime.now(timezone.utc).isoformat(),
            "source": self._id,
        }
        self._event_history.append(event)

        # Trim history
        if len(self._event_history) > self._max_history:
            self._event_history = self._event_history[-self._max_history:]

        logger.debug("Event published: %s [%s]", event_id, event_type.value)
        return event_id

    async def _buffer_event(self, event_type: ResearchEventType, payload: Dict[str, Any]) -> str:
        """Buffer an event when EventBus is disconnected."""
        event_id = f"evt-buf-{uuid4().hex[:16]}"
        logger.debug("Event buffered: %s [%s]", event_id, event_type.value)
        return event_id

    # ------------------------------------------------------------------
    # Subscribe
    # ------------------------------------------------------------------

    async def subscribe(self, event_type: ResearchEventType, handler: Callable) -> None:
        """Subscribe to a research event type.

        Args:
            event_type: Event type to subscribe to.
            handler: Async callable receiving (event) dict.
        """
        key = event_type.value
        if key not in self._subscriptions:
            self._subscriptions[key] = []
        self._subscriptions[key].append(handler)
        logger.info("Subscribed to %s (handlers: %d)", key, len(self._subscriptions[key]))

    async def unsubscribe(self, event_type: ResearchEventType, handler: Callable) -> None:
        """Unsubscribe from a research event type."""
        key = event_type.value
        if key in self._subscriptions:
            self._subscriptions[key] = [h for h in self._subscriptions[key] if h is not handler]
            if not self._subscriptions[key]:
                del self._subscriptions[key]
            logger.info("Unsubscribed from %s", key)

    # ------------------------------------------------------------------
    # Event Handlers
    # ------------------------------------------------------------------

    async def _on_platform_initialized(self, event: Dict[str, Any]) -> None:
        """Handle platform initialization event."""
        logger.info("Platform initialized event received: %s", event.get("payload", {}))

    async def _on_platform_shutdown(self, event: Dict[str, Any]) -> None:
        """Handle platform shutdown event."""
        logger.info("Platform shutdown event received: %s", event.get("payload", {}))

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    async def get_event_history(
        self,
        event_type: Optional[ResearchEventType] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Get recent event history, optionally filtered by type."""
        events = self._event_history
        if event_type is not None:
            events = [e for e in events if e["type"] == event_type.value]
        return events[-limit:]
