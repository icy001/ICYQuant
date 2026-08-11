"""OrderStateReducer — derives order state from events.

The reducer is a pure function: given a current state and an event,
it produces the next state. This is the core of event sourcing.

    state_0 + event_1 → state_1
    state_1 + event_2 → state_2
    ...
    state_n-1 + event_n → state_n (current)
"""
from __future__ import annotations

from typing import Any, Dict

from services.oms.events.order_event import OrderEvent
from services.oms.events.order_event_type import OrderEventType
from services.oms.domain.order_status import OrderStatus
from .order_projection import OrderProjection


class OrderStateReducer:
    """Pure function that reduces events to order state.

    This class is stateless — all state is passed in and returned.
    """

    # ── Event → Status mapping ─────────────────────

    _STATUS_MAP: Dict[OrderEventType, OrderStatus] = {
        OrderEventType.ORDER_ACCEPTED: OrderStatus.ACCEPTED,
        OrderEventType.ORDER_CREATED: OrderStatus.CREATED,
        OrderEventType.ORDER_ROUTING_STARTED: OrderStatus.ROUTING,
        OrderEventType.ORDER_WORKING: OrderStatus.WORKING,
        OrderEventType.ORDER_PARTIAL_FILL: OrderStatus.PARTIALLY_FILLED,
        OrderEventType.ORDER_FILLED: OrderStatus.FILLED,
        OrderEventType.ORDER_CANCELLED: OrderStatus.CANCELLED,
        OrderEventType.ORDER_REJECTED: OrderStatus.REJECTED,
        OrderEventType.ORDER_EXPIRED: OrderStatus.EXPIRED,
        OrderEventType.ORDER_FAILED: OrderStatus.FAILED,
        # Non-status-changing events
        OrderEventType.ORDER_CANCEL_REQUESTED: None,  # stays WORKING
        OrderEventType.ORDER_AMENDED: None,  # stays current
        OrderEventType.ORDER_SUSPENDED: None,
        OrderEventType.ORDER_RESUMED: None,
    }

    @staticmethod
    def reduce(state: OrderProjection,
               event: OrderEvent) -> OrderProjection:
        """Apply an event to a projection, returning a new state.

        This does NOT mutate the input state — it returns a new one.
        """
        # Create a copy
        new_state = OrderProjection(
            order_id=state.order_id,
            status=state.status,
            symbol=state.symbol,
            side=state.side,
            order_type=state.order_type,
            original_quantity=state.original_quantity,
            filled_quantity=state.filled_quantity,
            remaining_quantity=state.remaining_quantity,
            cancelled_quantity=state.cancelled_quantity,
            average_price=state.average_price,
            last_event_sequence=state.last_event_sequence,
            last_event_hash=state.last_event_hash,
            lineage_id=state.lineage_id,
            flow_id=state.flow_id,
            certificate_id=state.certificate_id,
            updated_at=state.updated_at,
            is_stale=state.is_stale,
        )

        # Apply event-specific logic
        reducer = _EVENT_HANDLERS.get(event.event_type)
        if reducer:
            reducer(new_state, event)

        # Update tracking fields
        new_state.last_event_sequence = event.sequence
        new_state.last_event_hash = event.event_hash
        new_state.updated_at = __import__("time").time()
        new_state.is_stale = False

        # Update lineage if not set
        if not new_state.lineage_id and event.lineage_id:
            new_state.lineage_id = event.lineage_id
            new_state.flow_id = event.flow_id
            new_state.certificate_id = event.certificate_id

        return new_state

    @staticmethod
    def reduce_all(events: list,
                   order_id: str = "") -> OrderProjection:
        """Reduce a list of events into a final projection.

        Starts from an empty state and applies each event in sequence.
        """
        state = OrderProjection.empty(order_id)
        for event in events:
            state = OrderStateReducer.reduce(state, event)
        return state

    @staticmethod
    def reduce_from_snapshot(snapshot,
                             events: list) -> OrderProjection:
        """Reduce events starting from a snapshot.

        `snapshot` is an EventStoreSnapshot.
        `events` are events after the snapshot sequence.
        """
        state = OrderProjection(
            order_id=snapshot.order_id,
            status=snapshot.status,
            original_quantity=snapshot.original_quantity,
            filled_quantity=snapshot.filled_quantity,
            remaining_quantity=snapshot.remaining_quantity,
            cancelled_quantity=snapshot.cancelled_quantity,
            average_price=snapshot.average_price,
            last_event_sequence=snapshot.sequence,
            last_event_hash=snapshot.last_event_hash,
        )
        for event in events:
            state = OrderStateReducer.reduce(state, event)
        return state


# ── Event handlers ────────────────────────────────────


def _handle_accepted(state: OrderProjection, event: OrderEvent) -> None:
    state.status = OrderStatus.ACCEPTED
    state.certificate_id = event.certificate_id


def _handle_created(state: OrderProjection, event: OrderEvent) -> None:
    state.status = OrderStatus.CREATED
    p = event.payload
    state.symbol = p.get("symbol", state.symbol)
    state.side = p.get("side", state.side)
    state.order_type = p.get("order_type", state.order_type)
    state.original_quantity = p.get("quantity", state.original_quantity)
    state.remaining_quantity = state.original_quantity
    state.filled_quantity = 0.0
    state.cancelled_quantity = 0.0


def _handle_routing(state: OrderProjection, event: OrderEvent) -> None:
    state.status = OrderStatus.ROUTING


def _handle_working(state: OrderProjection, event: OrderEvent) -> None:
    state.status = OrderStatus.WORKING


def _handle_partial_fill(state: OrderProjection, event: OrderEvent) -> None:
    state.status = OrderStatus.PARTIALLY_FILLED
    fill_qty = event.payload.get("fill_quantity", 0)
    fill_price = event.payload.get("fill_price", 0)

    # Update average price (VWAP)
    old_total = state.average_price * state.filled_quantity
    new_total = old_total + (fill_price * fill_qty)
    state.filled_quantity += fill_qty
    state.remaining_quantity -= fill_qty
    if state.filled_quantity > 0:
        state.average_price = new_total / state.filled_quantity


def _handle_filled(state: OrderProjection, event: OrderEvent) -> None:
    state.status = OrderStatus.FILLED
    fill_qty = event.payload.get("fill_quantity", 0)
    fill_price = event.payload.get("fill_price", 0)

    old_total = state.average_price * state.filled_quantity
    new_total = old_total + (fill_price * fill_qty)
    state.filled_quantity += fill_qty
    state.remaining_quantity -= fill_qty
    if state.filled_quantity > 0:
        state.average_price = new_total / state.filled_quantity


def _handle_cancelled(state: OrderProjection, event: OrderEvent) -> None:
    state.status = OrderStatus.CANCELLED
    cancelled = event.payload.get("cancelled_quantity",
                                  state.remaining_quantity)
    state.cancelled_quantity += cancelled
    state.remaining_quantity -= cancelled


def _handle_rejected(state: OrderProjection, event: OrderEvent) -> None:
    state.status = OrderStatus.REJECTED


def _handle_expired(state: OrderProjection, event: OrderEvent) -> None:
    state.status = OrderStatus.EXPIRED
    state.cancelled_quantity += state.remaining_quantity
    state.remaining_quantity = 0


def _handle_failed(state: OrderProjection, event: OrderEvent) -> None:
    state.status = OrderStatus.FAILED


def _handle_amended(state: OrderProjection, event: OrderEvent) -> None:
    new_qty = event.payload.get("new_quantity", 0)
    if new_qty > 0:
        delta = new_qty - state.original_quantity
        state.original_quantity = new_qty
        state.remaining_quantity += delta


_EVENT_HANDLERS = {
    OrderEventType.ORDER_ACCEPTED: _handle_accepted,
    OrderEventType.ORDER_CREATED: _handle_created,
    OrderEventType.ORDER_ROUTING_STARTED: _handle_routing,
    OrderEventType.ORDER_WORKING: _handle_working,
    OrderEventType.ORDER_PARTIAL_FILL: _handle_partial_fill,
    OrderEventType.ORDER_FILLED: _handle_filled,
    OrderEventType.ORDER_CANCELLED: _handle_cancelled,
    OrderEventType.ORDER_REJECTED: _handle_rejected,
    OrderEventType.ORDER_EXPIRED: _handle_expired,
    OrderEventType.ORDER_FAILED: _handle_failed,
    OrderEventType.ORDER_AMENDED: _handle_amended,
}
