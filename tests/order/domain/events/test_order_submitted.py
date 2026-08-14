"""Tests for ORDER_SUBMITTED (Commit 33 Part 1.4 #11)."""

from __future__ import annotations

from services.order.domain.events import OrderSubmitted


def test_event_type(make_event):
    assert make_event(OrderSubmitted).event_type == "ORDER_SUBMITTED"


def test_submitted_carries_client_and_execution_ids(make_event):
    event = make_event(
        OrderSubmitted,
        client_order_id="ICY-ORD-20260813-000001",
        execution_request_id="EXREQ-20260813-000001",
    )
    assert event.client_order_id == "ICY-ORD-20260813-000001"
    assert event.execution_request_id == "EXREQ-20260813-000001"


def test_submitted_payload_fields_are_optional(make_event):
    event = make_event(OrderSubmitted)
    assert event.client_order_id is None
    assert event.execution_request_id is None
