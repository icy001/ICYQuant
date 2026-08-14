"""Order event envelope for the reliable outbox layer (Commit 33 Part 1.5).

Part 1.4 built the domain events (:class:`OrderEvent`) and the bus-facing
:class:`~services.order.engine.event_mapper.EventEnvelope`.  Part 1.5 adds the
record the transactional outbox actually stages - :class:`OrderEventEnvelope` -
which is what
:class:`~services.order.engine.outbox.service.OutboxService` persists inside the
same transaction boundary as the order state change (#10):

.. code-block:: text

    Order (persisted)
        -> domain event       (EventMapper.to_event)
        -> OrderEventEnvelope  (envelope_from_event)
        -> OutboxMessage       (OutboxService.stage)
        -> OutboxRepository.append

The envelope mirrors the domain event: identity, aggregate, lineage
(correlation / causation), the per-aggregate version and the payload.  It is
immutable - a new fact means a new envelope, never a mutated one (#24).
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional

from services.order.domain.events.base import OrderEvent

#: Fields that belong on the envelope itself; everything else is payload.
_ENVELOPE_OWN_FIELDS = {
    "event_id",
    "event_type",
    "aggregate_id",
    "aggregate_type",
    "order_id",
    "order_request_id",
    "aggregate_version",
    "correlation_id",
    "causation_id",
    "occurred_at",
    "sequence",
    "payload_version",
}


class EnvelopeBuildError(ValueError):
    """Raised when a domain event cannot be turned into an outbox envelope."""


@dataclass(frozen=True)
class OrderEventEnvelope:
    """The immutable record handed to the transactional outbox (#4).

    ``aggregate_version`` is the per-aggregate monotonic version of the event -
    for orders it equals the domain event ``sequence`` (1, 2, 3, ...) so the
    outbox can protect stream ordering and reconciliation can spot gaps (#9).
    """

    event_id: str
    event_type: str
    aggregate_id: str
    aggregate_type: str
    order_id: str
    order_request_id: str
    aggregate_version: int
    correlation_id: str
    causation_id: Optional[str]
    occurred_at: datetime
    payload: Dict[str, Any]

    def __post_init__(self) -> None:
        if not self.event_id:
            raise ValueError("event_id is required")
        if not self.aggregate_id:
            raise ValueError("aggregate_id is required")
        if not self.order_id:
            raise ValueError("order_id is required")
        if not self.order_request_id:
            raise ValueError("order_request_id is required")
        if not self.correlation_id:
            raise ValueError("correlation_id is required")
        if self.aggregate_version < 1:
            raise ValueError("aggregate_version must be a positive integer")


def envelope_from_event(
    event: OrderEvent,
    aggregate_version: Optional[int] = None,
    payload: Optional[Dict[str, Any]] = None,
) -> OrderEventEnvelope:
    """Build an outbox-ready envelope from an order domain event.

    ``aggregate_version`` defaults to the event's ``sequence``; ``payload``
    defaults to the event's non-envelope dataclass fields (e.g.
    ``venue_order_id`` / ``reject_reason`` / ``client_order_id`` /
    ``execution_request_id``).  Nothing is invented - every value is copied
    from the event as-is.
    """
    if aggregate_version is None:
        aggregate_version = event.sequence
    if payload is None:
        payload = _extract_payload(event)
    occurred_at = event.occurred_at
    if occurred_at is None:  # pragma: no cover - enforced by OrderEvent
        raise EnvelopeBuildError("occurred_at is required on the domain event")
    return OrderEventEnvelope(
        event_id=event.event_id,
        event_type=event.event_type,
        aggregate_id=event.aggregate_id,
        aggregate_type=event.aggregate_type,
        order_id=event.order_id,
        order_request_id=event.order_request_id,
        aggregate_version=aggregate_version,
        correlation_id=event.correlation_id,
        causation_id=event.causation_id,
        occurred_at=occurred_at,
        payload=dict(payload),
    )


def _extract_payload(event: OrderEvent) -> Dict[str, Any]:
    payload: Dict[str, Any] = {}
    for field in dataclasses.fields(event):
        if field.name in _ENVELOPE_OWN_FIELDS:
            continue
        payload[field.name] = getattr(event, field.name)
    return payload
