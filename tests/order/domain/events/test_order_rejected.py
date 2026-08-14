"""Tests for ORDER_REJECTED (Commit 33 Part 1.4 #13)."""

from __future__ import annotations

from services.order.domain.events import OrderRejected


def test_event_type(make_event):
    assert make_event(OrderRejected).event_type == "ORDER_REJECTED"


def test_rejected_carries_the_reason(make_event):
    event = make_event(OrderRejected, reject_reason="BROKER_UNAVAILABLE")
    assert event.reject_reason == "BROKER_UNAVAILABLE"


def test_rejected_has_no_venue_or_execution_ids(make_event):
    event = make_event(OrderRejected)
    assert not hasattr(event, "venue_order_id")
    assert not hasattr(event, "execution_request_id")
