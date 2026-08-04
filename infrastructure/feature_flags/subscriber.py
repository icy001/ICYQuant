"""
Feature flag event subscriber.

Provides pre-built subscribers for common
ICYQuant systems that need to react to
feature flag changes.

Default subscribers include:
    - OMS (Order Management System)
    - Risk Engine
    - Execution Engine
    - Strategy Engine
    - Gateway
    - Research
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Dict, List, Optional

from .events import EventBus, FeatureEvent, FeatureEventType

logger = logging.getLogger(__name__)


class SubscriberType:
    """Pre-defined subscriber types for ICYQuant systems."""

    OMS = "oms"
    RISK = "risk"
    EXECUTION = "execution"
    STRATEGY = "strategy"
    GATEWAY = "gateway"
    RESEARCH = "research"


class FeatureEventSubscriber:
    """
    Subscribes to feature flag events and dispatches
    them to registered handlers.

    Supports pre-defined subscriber types for
    ICYQuant systems and custom handlers.

    Usage:
        subscriber = FeatureEventSubscriber(bus)
        subscriber.register(SubscriberType.OMS, oms_handler)
        await subscriber.subscribe_all()
    """

    def __init__(
        self,
        event_bus: Optional[EventBus] = None,
    ) -> None:
        """
        Initialize subscriber.

        Args:
            event_bus: EventBus instance.
        """
        self._bus = event_bus or EventBus()
        self._handlers: Dict[str, List[Callable]] = {}
        self._subscribed = False
        self._handled_count = 0
        self._error_count = 0

    @property
    def bus(self) -> EventBus:
        """Get the underlying EventBus."""
        return self._bus

    def register(
        self,
        subscriber_type: str,
        handler: Callable,
    ) -> None:
        """
        Register a handler for a subscriber type.

        Args:
            subscriber_type: Type of subscriber (e.g., 'oms', 'risk').
            handler: Async handler function.
        """
        if subscriber_type not in self._handlers:
            self._handlers[subscriber_type] = []
        self._handlers[subscriber_type].append(handler)

    def unregister(
        self,
        subscriber_type: str,
        handler: Callable,
    ) -> None:
        """
        Unregister a handler for a subscriber type.

        Args:
            subscriber_type: Type of subscriber.
            handler: Handler to remove.
        """
        if subscriber_type in self._handlers:
            self._handlers[subscriber_type] = [
                h for h in self._handlers[subscriber_type] if h != handler
            ]

    async def subscribe_all(self) -> None:
        """
        Subscribe to all feature flag event types.

        Registers handlers for all known event types
        and dispatches to registered subscriber handlers.
        """
        event_types = list(FeatureEventType)
        for event_type in event_types:
            await self._bus.subscribe(event_type, self._dispatch)

        # Also subscribe to wildcard for system events
        await self._bus.subscribe_all(self._dispatch_all)
        self._subscribed = True

        logger.info(
            "Subscribed to %d event types with %d subscriber types",
            len(event_types),
            len(self._handlers),
        )

    async def _dispatch(self, event: FeatureEvent) -> None:
        """Dispatch a specific event to registered handlers."""
        for subscriber_type, handlers in self._handlers.items():
            for handler in handlers:
                try:
                    result = handler(event)
                    if asyncio.iscoroutine(result):
                        await result
                    self._handled_count += 1
                except Exception as e:
                    self._error_count += 1
                    logger.error(
                        "Subscriber handler error for %s/%s: %s",
                        subscriber_type,
                        event.event_type.value,
                        e,
                    )

    async def _dispatch_all(self, event: FeatureEvent) -> None:
        """Dispatch all events to registered handlers."""
        # System-wide handlers get all events
        for subscriber_type, handlers in self._handlers.items():
            for handler in handlers:
                try:
                    result = handler(event)
                    if asyncio.iscoroutine(result):
                        await result
                    self._handled_count += 1
                except Exception as e:
                    self._error_count += 1
                    logger.error(
                        "Wildcard handler error for %s: %s",
                        subscriber_type,
                        e,
                    )

    async def subscribe_to(
        self,
        event_type: FeatureEventType,
        handler: Callable,
    ) -> None:
        """
        Subscribe to a specific event type with a handler.

        Args:
            event_type: Event type to subscribe to.
            handler: Handler function.
        """
        await self._bus.subscribe(event_type, handler)
        self._subscribed = True

    def get_subscriber_types(self) -> List[str]:
        """Get all registered subscriber types."""
        return list(self._handlers.keys())

    def is_subscribed(self) -> bool:
        """Check if subscribed to events."""
        return self._subscribed

    def get_stats(self) -> Dict[str, Any]:
        """Get subscriber statistics."""
        return {
            "subscribed": self._subscribed,
            "subscriber_types": list(self._handlers.keys()),
            "handled_count": self._handled_count,
            "error_count": self._error_count,
            "event_bus_stats": self._bus.get_stats(),
        }

    async def shutdown(self) -> None:
        """Shutdown subscriber and event bus."""
        self._subscribed = False
        self._handlers.clear()
        await self._bus.shutdown()
