"""Order request event factory.

The factory is the single place that assembles an
:class:`~services.order.request.events.OrderRequestEvent`:

- event id (globally unique, never the aggregate id)
- aggregate type / aggregate id (``OrderRequest`` / order request id)
- correlation id (from the request, keeps the whole trading chain linked)
- causation id (the event that caused this one)
- sequence (aggregate-local, monotonic)
- timestamp
- payload (minimal business facts — an event describes facts, not a copy of
  the database)

Business code never builds events by hand.
"""

from __future__ import annotations

import itertools
from typing import Any, Callable, Dict, Optional

from services.order.request.event_types import OrderRequestEventType
from services.order.request.events import OrderRequestEvent
from services.order.request.model import OrderRequest
from services.order.request.state import OrderRequestState

#: Stable aggregate type used on every order request event.
AGGREGATE_TYPE = "OrderRequest"

#: Maps an event type to the aggregate state *after* the event was applied.
_STATE_AFTER_EVENT: Dict[OrderRequestEventType, OrderRequestState] = {
    OrderRequestEventType.ORDER_REQUEST_CREATED: OrderRequestState.CREATED,
    OrderRequestEventType.ORDER_REQUEST_VALIDATED: OrderRequestState.VALIDATED,
    OrderRequestEventType.ORDER_REQUEST_NORMALIZED: OrderRequestState.NORMALIZED,
    OrderRequestEventType.ORDER_REQUEST_SUBMITTED: OrderRequestState.SUBMITTED,
    OrderRequestEventType.ORDER_REQUEST_ACCEPTED: OrderRequestState.ACCEPTED,
    OrderRequestEventType.ORDER_REQUEST_REJECTED: OrderRequestState.REJECTED,
    OrderRequestEventType.ORDER_REQUEST_CANCELLED: OrderRequestState.CANCELLED,
    OrderRequestEventType.ORDER_REQUEST_EXPIRED: OrderRequestState.EXPIRED,
    OrderRequestEventType.ORDER_REQUEST_HANDOFF: OrderRequestState.HANDOFF,
}

_event_id_counter = itertools.count(1)


def new_event_id() -> str:
    """Return a new globally unique event id (e.g. ``EVT-000001``).

    The counter is monotonic and shared by every factory instance so ids stay
    unique across aggregates.
    """
    return f"EVT-{next(_event_id_counter):06d}"


#: Business facts every order request event carries.
_LINEAGE_FIELDS = (
    "intent_id",
    "authorization_id",
    "certificate_id",
    "decision_id",
    "strategy_id",
    "session_id",
    "signal_id",
    "correlation_id",
)

_EXECUTION_FIELDS = (
    "symbol",
    "side",
    "quantity",
    "order_type",
    "time_in_force",
    "limit_price",
)


class OrderRequestEventFactory:
    """Builds immutable :class:`OrderRequestEvent` instances."""

    def __init__(self, *, event_id_generator: Optional[Callable[[], str]] = None) -> None:
        self._event_id_generator: Callable[[], str] = (
            event_id_generator if event_id_generator is not None else new_event_id
        )

    def create(
        self,
        request: OrderRequest,
        event_type: OrderRequestEventType,
        *,
        sequence: int,
        causation_id: Optional[str],
        timestamp: float,
        reason: Optional[str] = None,
    ) -> OrderRequestEvent:
        """Create a domain event for ``request``.

        ``sequence`` must be positive and increasing for the aggregate;
        ``causation_id`` is the event id that caused this event (``None`` only
        for the first event of an aggregate).  ``reason`` is included in the
        payload for terminal events (reject / cancel / expire).
        """
        if sequence <= 0:
            raise ValueError("event sequence must be a positive integer")
        if not request.order_request_id:
            raise ValueError("request.order_request_id must not be empty")

        return OrderRequestEvent(
            event_id=self._event_id_generator(),
            event_type=event_type,
            aggregate_id=request.order_request_id,
            aggregate_type=AGGREGATE_TYPE,
            correlation_id=request.correlation_id,
            causation_id=causation_id,
            sequence=sequence,
            timestamp=timestamp,
            state=self._state_after(event_type),
            payload=self._build_payload(request, event_type=event_type, reason=reason),
        )

    @staticmethod
    def _state_after(event_type: OrderRequestEventType) -> OrderRequestState:
        try:
            return _STATE_AFTER_EVENT[event_type]
        except KeyError:
            raise ValueError(f"unsupported event type: {event_type!r}") from None

    @staticmethod
    def _build_payload(
        request: OrderRequest,
        *,
        event_type: OrderRequestEventType,
        reason: Optional[str],
    ) -> Dict[str, Any]:
        """Minimal payload: identity, lineage and execution facts.

        An event describes facts; it must not copy risk engine / strategy /
        portfolio / position / account state.
        """
        payload: Dict[str, Any] = {"order_request_id": request.order_request_id}
        for field_name in _LINEAGE_FIELDS:
            payload[field_name] = getattr(request, field_name)
        for field_name in _EXECUTION_FIELDS:
            payload[field_name] = getattr(request, field_name)
        if reason is not None:
            payload["reason"] = reason
        return payload


__all__ = [
    "AGGREGATE_TYPE",
    "OrderRequestEventFactory",
    "new_event_id",
]
