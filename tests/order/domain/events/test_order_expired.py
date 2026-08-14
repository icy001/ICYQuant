"""Tests for ORDER_EXPIRED (Commit 33 Part 1.4 #16)."""

from __future__ import annotations

from services.order.domain.events import OrderExpired


def test_event_type(make_event):
    assert make_event(OrderExpired).event_type == "ORDER_EXPIRED"


def test_expired_event_has_no_extra_payload(make_event):
    event = make_event(OrderExpired)
    for field in (
        "venue_order_id",
        "execution_request_id",
        "reject_reason",
        "client_order_id",
    ):
        assert not hasattr(event, field)
