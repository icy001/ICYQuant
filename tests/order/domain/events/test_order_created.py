"""Tests for ORDER_CREATED (Commit 33 Part 1.4 #10)."""

from __future__ import annotations

import dataclasses

import pytest

from services.order.domain.events import OrderCreated


def test_event_type(make_event):
    assert make_event(OrderCreated).event_type == "ORDER_CREATED"


def test_created_event_is_frozen(make_event):
    with pytest.raises(dataclasses.FrozenInstanceError):
        make_event(OrderCreated).event_id = "EVT-ORD-999999"


def test_created_event_carries_the_handoff_identity(make_event):
    event = make_event(
        OrderCreated,
        event_id="EVT-ORD-000001",
        order_id="ORD-20260813-000001",
        order_request_id="OR-20260813-000001",
    )
    assert event.order_id == "ORD-20260813-000001"
    assert event.order_request_id == "OR-20260813-000001"


def test_created_event_has_no_execution_payload(make_event):
    event = make_event(OrderCreated)
    for field in ("venue_order_id", "execution_request_id", "reject_reason"):
        assert not hasattr(event, field)
