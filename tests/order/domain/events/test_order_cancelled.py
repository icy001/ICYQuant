"""Tests for ORDER_CANCELLED (Commit 33 Part 1.4 #15)."""

from __future__ import annotations

from services.order.domain.events import OrderCancelled


def test_event_type(make_event):
    assert make_event(OrderCancelled).event_type == "ORDER_CANCELLED"


def test_cancelled_carries_the_execution_request_id(make_event):
    event = make_event(OrderCancelled, execution_request_id="EXREQ-CANCEL-1")
    assert event.execution_request_id == "EXREQ-CANCEL-1"


def test_cancelled_is_a_confirmed_fact(make_event):
    # #15: only produced after the venue confirms the cancellation.
    event = make_event(OrderCancelled)
    assert event.event_type == "ORDER_CANCELLED"
    assert event.event_type != "ORDER_CANCEL_PENDING"
