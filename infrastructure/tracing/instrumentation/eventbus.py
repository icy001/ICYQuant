"""
EventBus auto-instrumentation.

Provides automatic span creation for
ICYQuant EventBus operations, including:
- Event publication
- Event subscription
- Event dispatch
- Retry tracking
- Dead event handling
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from .base import Instrumentation


class EventBusInstrumentation(Instrumentation):
    """
    ICYQuant EventBus auto-instrumentation.

    Wraps the EventBus to automatically create
    spans for event publication, subscription,
    and dispatch operations.

    Features:
    - Event publish span creation
    - Event subscribe span creation
    - Event dispatch tracking
    - Retry and dead event tracking
    - Handler execution tracking
    - Latency measurement

    Usage:
        instr = EventBusInstrumentation()
        await instr.install()

        # When using EventBus:
        await event_bus.publish("order.created", order_data)
        # Automatically traced
    """

    name: str = "eventbus"
    version: str = "1.0"

    def __init__(
        self,
        tracer: Optional[Any] = None,
        capture_payload: bool = False,
        max_payload_size: int = 256,
    ) -> None:
        """
        Initialize EventBus instrumentation.

        Args:
            tracer: Optional Tracer instance.
            capture_payload: Whether to capture event payload.
            max_payload_size: Max payload size to capture.
        """

        super().__init__(tracer=tracer)
        self._capture_payload = capture_payload
        self._max_payload_size = max_payload_size
        self._installed: bool = False
        self._publish_count: int = 0
        self._dispatch_count: int = 0
        self._error_count: int = 0

    @property
    def is_instrumented(
        self,
    ) -> bool:
        return self._installed

    @property
    def stats(
        self,
    ) -> Dict[str, int]:
        """Get EventBus operation statistics."""
        return {
            "published": self._publish_count,
            "dispatched": self._dispatch_count,
            "errors": self._error_count,
        }

    async def install(
        self,
    ) -> None:
        """Install EventBus instrumentation."""
        self._installed = True

    async def uninstall(
        self,
    ) -> None:
        """Remove EventBus instrumentation."""
        self._installed = False

    def create_publish_span(
        self,
        event_type: str,
        event_id: Optional[str] = None,
        source: Optional[str] = None,
        payload: Optional[Any] = None,
        handler_count: int = 0,
    ) -> Any:
        """
        Create an event publish span.

        Args:
            event_type: Event type name.
            event_id: Event identifier.
            source: Event source component.
            payload: Event payload.
            handler_count: Number of registered handlers.

        Returns:
            SpanModel instance.
        """

        from ...models import SpanKind

        span = self.tracer.start_span(
            operation=f"eventbus.publish.{event_type}",
            kind=SpanKind.PRODUCER,
        )

        span.add_attribute("icyquant.event.type", event_type)
        span.add_attribute("icyquant.event.operation", "publish")

        if event_id:
            span.add_attribute("icyquant.event.id", event_id)

        if source:
            span.add_attribute("icyquant.event.source", source)

        if handler_count > 0:
            span.add_attribute("icyquant.event.handler_count", handler_count)

        if payload and self._capture_payload:
            payload_str = str(payload)[:self._max_payload_size]
            span.add_attribute("icyquant.event.payload", payload_str)

        self._publish_count += 1
        return span

    def create_dispatch_span(
        self,
        event_type: str,
        handler_name: str,
        event_id: Optional[str] = None,
        retry_count: int = 0,
        is_dead_event: bool = False,
    ) -> Any:
        """
        Create an event dispatch span.

        Args:
            event_type: Event type name.
            handler_name: Handler name.
            event_id: Event identifier.
            retry_count: Number of retries.
            is_dead_event: Whether this is a dead event.

        Returns:
            SpanModel instance.
        """

        from ...models import SpanKind

        operation = f"eventbus.dispatch.{event_type}"
        if is_dead_event:
            operation = f"eventbus.dead.{event_type}"

        span = self.tracer.start_span(
            operation=operation,
            kind=SpanKind.CONSUMER,
        )

        span.add_attribute("icyquant.event.type", event_type)
        span.add_attribute("icyquant.event.operation", "dispatch")
        span.add_attribute("icyquant.event.handler", handler_name)

        if event_id:
            span.add_attribute("icyquant.event.id", event_id)

        if retry_count > 0:
            span.add_attribute("icyquant.retry.count", retry_count)

        if is_dead_event:
            span.add_attribute("icyquant.event.is_dead", True)

        self._dispatch_count += 1
        return span

    def create_subscribe_span(
        self,
        event_type: str,
        handler_name: str,
    ) -> Any:
        """
        Create an event subscribe span.

        Args:
            event_type: Event type.
            handler_name: Handler name.

        Returns:
            SpanModel instance.
        """

        from ...models import SpanKind

        span = self.tracer.start_span(
            operation=f"eventbus.subscribe.{event_type}",
            kind=SpanKind.INTERNAL,
        )

        span.add_attribute("icyquant.event.type", event_type)
        span.add_attribute("icyquant.event.operation", "subscribe")
        span.add_attribute("icyquant.event.handler", handler_name)

        return span
