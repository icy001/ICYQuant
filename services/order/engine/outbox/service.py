"""Outbox application service (Commit 33 Part 1.5 #4 / #10)."""

from __future__ import annotations

from datetime import datetime, timezone

from services.order.engine.events import OrderEventEnvelope

from .model import OutboxMessage
from .repository import OutboxRepository


class OutboxService:
    """Stages an order event inside the same transaction as the order change.

    ``stage`` persists the event as an :class:`OutboxMessage` with
    ``message_id == event_id``, making the outbox/event idempotency relation
    natural (#4): appending the same event twice is a duplicate, never a copy.
    """

    def __init__(self, repository: OutboxRepository) -> None:
        self.repository = repository

    def stage(self, event: OrderEventEnvelope) -> OutboxMessage:
        message = OutboxMessage(
            message_id=event.event_id,
            aggregate_id=event.order_id,
            aggregate_type=event.aggregate_type,
            aggregate_version=event.aggregate_version,
            event_id=event.event_id,
            event_type=event.event_type,
            correlation_id=event.correlation_id,
            causation_id=event.causation_id,
            payload=event.payload,
            occurred_at=event.occurred_at,
            created_at=datetime.now(timezone.utc),
        )
        self.repository.append(message)
        return message
