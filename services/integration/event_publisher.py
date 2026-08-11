"""
Event Publisher — base class and registry for all domain
event producers.

Every domain that **owns** events must publish through this
abstraction.  The publisher wraps raw domain events in an
EventEnvelope before placing them on the bus.

Architecture principle:

    Domain Aggregate creates Domain Event
              |
              v
    EventPublisher wraps in EventEnvelope
              |
              v
    Event Bus delivers to consumers
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, List, Mapping, Optional

from services.integration.event_envelope import EventEnvelope

logger = logging.getLogger(__name__)


class EventPublisher(ABC):
    """
    Abstract base for domain event publishers.

    Each domain (OMS, Position, Ledger, etc.) should subclass
    this and implement ``_publish_envelope``.

    Usage::

        class OMSEventPublisher(EventPublisher):
            async def _publish_envelope(self, envelope: EventEnvelope) -> None:
                await self._bus.publish(envelope.to_dict())
    """

    def __init__(self, producer: str) -> None:
        self._producer = producer
        self._published: List[EventEnvelope] = []

    @property
    def producer(self) -> str:
        return self._producer

    # ── publish ───────────────────────────────────────────────────────

    def publish(
        self,
        event_type: str,
        aggregate_type: str,
        aggregate_id: str,
        aggregate_version: int,
        payload: Mapping[str, Any],
        *,
        event_id: Optional[str] = None,
        event_version: int = 1,
        correlation_id: str = "",
        causation_id: Optional[str] = None,
        lineage_id: str = "",
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> EventEnvelope:
        """
        Build an envelope and publish it.

        Returns the envelope so callers can inspect / log it.
        """
        envelope = EventEnvelope.from_event(
            event_id=event_id or EventEnvelope().event_id,
            event_type=event_type,
            event_version=event_version,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            aggregate_version=aggregate_version,
            producer=self._producer,
            payload=payload,
            correlation_id=correlation_id,
            causation_id=causation_id,
            lineage_id=lineage_id,
            metadata=metadata,
        )

        self._do_publish(envelope)
        return envelope

    def publish_envelope(self, envelope: EventEnvelope) -> EventEnvelope:
        """Publish a pre-built envelope directly."""
        self._do_publish(envelope)
        return envelope

    def _do_publish(self, envelope: EventEnvelope) -> None:
        """Internal publish with logging and tracking."""
        logger.info(
            "Publishing event: type=%s id=%s producer=%s aggregate=%s v%d",
            envelope.event_type,
            envelope.event_id,
            envelope.producer,
            envelope.aggregate_id,
            envelope.aggregate_version,
        )
        self._published.append(envelope)
        self._publish_envelope(envelope)

    @abstractmethod
    def _publish_envelope(self, envelope: EventEnvelope) -> None:
        """
        Send the envelope to the underlying transport.

        Subclasses must implement this (e.g. write to Kafka, Redis, etc.).
        """

    # ── inspection ────────────────────────────────────────────────────

    @property
    def published_events(self) -> List[EventEnvelope]:
        """All events published by this publisher (for testing)."""
        return list(self._published)

    def clear_history(self) -> None:
        """Reset the published event history."""
        self._published.clear()
