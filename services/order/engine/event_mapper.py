"""Order event mapping (Commit 33 Part 1.4 #17 / #27).

The mapper is the pure bridge:

.. code-block:: text

    Order (already transitioned + persisted)
        -> domain event   (EventMapper.to_event)
        -> EventEnvelope  (EventMapper.to_envelope)

It performs no state changes and no persistence.  The caller (the engine
service, wired in a later step) must follow the fail-closed order:

    Validate -> Change State -> Persist -> Create Event -> Publish Event (#21)

and must never fabricate an event from an UNKNOWN execution response - the
order stays SUBMITTED and no ORDER_ACCEPTED is produced (#22).

The mapper only maps the 7 lifecycle statuses that have a domain event.  The
internal ``PENDING_SUBMIT`` state and the fill states (``PARTIALLY_FILLED`` /
``FILLED``) have no event here and raise :class:`EventMappingError`.
"""

from __future__ import annotations

import dataclasses
from datetime import datetime
from typing import Dict, Optional, Type

from services.order.domain.events import (
    OrderAccepted,
    OrderCancelPending,
    OrderCancelled,
    OrderCreated,
    OrderEvent,
    OrderExpired,
    OrderRejected,
    OrderSubmitted,
)
from services.order.domain.order import Order
from services.order.domain.order_status import OrderStatus

#: Fields carried by the envelope itself - everything else is payload.
_ENVELOPE_FIELDS = {
    "event_id",
    "event_type",
    "aggregate_type",
    "aggregate_id",
    "correlation_id",
    "causation_id",
    "sequence",
    "occurred_at",
    "payload_version",
}


class EventMappingError(ValueError):
    """Raised when a state has no domain event or a payload is missing."""


@dataclasses.dataclass(frozen=True)
class EventEnvelope:
    """The unified record an event bus receives (#27).

    The bus only needs to understand this envelope - it never needs to know
    about Order / Position / Ledger aggregates.
    """

    event_id: str
    event_type: str
    aggregate_type: str
    aggregate_id: str
    correlation_id: str
    causation_id: Optional[str]
    sequence: int
    occurred_at: datetime
    payload_version: int
    payload: dict


_STATUS_TO_EVENT: Dict[OrderStatus, Type[OrderEvent]] = {
    OrderStatus.CREATED: OrderCreated,
    OrderStatus.SUBMITTED: OrderSubmitted,
    OrderStatus.ACCEPTED: OrderAccepted,
    OrderStatus.REJECTED: OrderRejected,
    OrderStatus.CANCEL_PENDING: OrderCancelPending,
    OrderStatus.CANCELLED: OrderCancelled,
    OrderStatus.EXPIRED: OrderExpired,
}


class EventMapper:
    """Maps order state transitions to domain events and bus envelopes."""

    def event_class_for(self, status: OrderStatus) -> Type[OrderEvent]:
        """The domain event class for a lifecycle status."""
        try:
            return _STATUS_TO_EVENT[status]
        except KeyError:
            raise EventMappingError(
                f"no domain event mapped for order status {status.value}"
            ) from None

    def to_event(
        self,
        order: Order,
        status: OrderStatus,
        *,
        event_id: str,
        sequence: int,
        causation_id: Optional[str] = None,
        occurred_at: Optional[datetime] = None,
        execution_request_id: Optional[str] = None,
    ) -> OrderEvent:
        """Build the domain event for an *already transitioned* order.

        The event is created from the new order state: identity, lineage,
        correlation and the payload fields (``venue_order_id`` /
        ``reject_reason`` / ``client_order_id`` / ``execution_request_id``)
        are copied as-is - never invented.
        """
        event_class = self.event_class_for(status)
        occurred_at = occurred_at or order.updated_at
        base = dict(
            event_id=event_id,
            aggregate_type="ORDER",
            aggregate_id=order.order_id,
            order_id=order.order_id,
            order_request_id=order.order_request_id,
            correlation_id=order.correlation_id,
            causation_id=causation_id,
            occurred_at=occurred_at,
            sequence=sequence,
            payload_version=1,
        )
        payload = self._payload_for(event_class, order, execution_request_id)
        return event_class(**base, **payload)

    def to_envelope(self, event: OrderEvent) -> EventEnvelope:
        """Flatten a domain event into the unified bus envelope."""
        payload: Dict[str, object] = {}
        for field in dataclasses.fields(event):
            if field.name in _ENVELOPE_FIELDS:
                continue
            payload[field.name] = getattr(event, field.name)
        return EventEnvelope(
            event_id=event.event_id,
            event_type=event.event_type,
            aggregate_type=event.aggregate_type,
            aggregate_id=event.aggregate_id,
            correlation_id=event.correlation_id,
            causation_id=event.causation_id,
            sequence=event.sequence,
            occurred_at=event.occurred_at,
            payload_version=event.payload_version,
            payload=payload,
        )

    @staticmethod
    def _payload_for(
        event_class: Type[OrderEvent],
        order: Order,
        execution_request_id: Optional[str],
    ) -> dict:
        """Copy only the payload fields the concrete event actually declares."""
        field_names = {field.name for field in dataclasses.fields(event_class)}
        payload: Dict[str, object] = {}
        if "client_order_id" in field_names:
            payload["client_order_id"] = order.client_order_id
        if "venue_order_id" in field_names:
            payload["venue_order_id"] = order.venue_order_id
        if "reject_reason" in field_names:
            if order.reject_reason is None:
                # Spec #13: a REJECTED event without a reason is not a valid fact.
                raise EventMappingError(
                    "ORDER_REJECTED requires a reject_reason on the order"
                )
            payload["reject_reason"] = order.reject_reason
        if "execution_request_id" in field_names:
            payload["execution_request_id"] = execution_request_id
        return payload
