"""Tests for ORDER_CANCEL_PENDING (Commit 33 Part 1.4 #14)."""

from __future__ import annotations

from services.order.domain.events import OrderCancelPending


def test_event_type(make_event):
    assert make_event(OrderCancelPending).event_type == "ORDER_CANCEL_PENDING"


def test_cancel_pending_carries_the_execution_request_id(make_event):
    event = make_event(OrderCancelPending, execution_request_id="EXREQ-CANCEL-1")
    assert event.execution_request_id == "EXREQ-CANCEL-1"


def test_cancel_pending_is_not_cancelled(make_event):
    # #14: this event says the request was SENT, never that the order is gone.
    event = make_event(OrderCancelPending)
    assert event.event_type == "ORDER_CANCEL_PENDING"
    assert event.event_type != "ORDER_CANCELLED"
