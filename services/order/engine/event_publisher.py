"""Order event publisher boundary (Commit 33 Part 1.4 #18 / #19).

The order engine never talks to Kafka / RabbitMQ / Redis directly - it only
depends on :class:`OrderEventPublisher`.  The bus implementation can be swapped
without touching the order domain:

.. code-block:: text

    Order Engine -> OrderEventPublisher -> Event Bus

Consumers (Position / Ledger / TradeBook / Reconciliation) are NOT implemented
here - they belong to later commits (#26).
"""

from __future__ import annotations

from typing import List, Optional, Protocol, runtime_checkable

from services.order.domain.events.base import OrderEvent


class EventPublishError(RuntimeError):
    """Raised when an event cannot be delivered to the bus."""


@runtime_checkable
class OrderEventPublisher(Protocol):
    """Stable contract between the order engine and the event bus."""

    def publish(self, event: OrderEvent) -> None: ...


class InMemoryEventPublisher:
    """In-memory publisher for tests / paper trading.

    ``fail_on_publish`` injects a delivery failure so the engine's fail-closed
    behaviour (never pretend an event was published) can be verified.
    """

    def __init__(self) -> None:
        self._published: List[OrderEvent] = []
        self.fail_on_publish = False

    def publish(self, event: OrderEvent) -> None:
        if self.fail_on_publish:
            raise EventPublishError("event publisher unavailable (injected)")
        self._published.append(event)

    @property
    def events(self) -> List[OrderEvent]:
        """All published events, in publication order."""
        return list(self._published)

    def published(self, event_type: Optional[str] = None) -> List[OrderEvent]:
        """Published events, optionally filtered by ``event_type``."""
        if event_type is None:
            return list(self._published)
        return [event for event in self._published if event.event_type == event_type]
