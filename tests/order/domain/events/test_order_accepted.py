"""Tests for ORDER_ACCEPTED (Commit 33 Part 1.4 #12 / #24)."""

from __future__ import annotations

import dataclasses

import pytest

from services.order.domain.events import OrderAccepted


def test_event_type(make_event):
    assert make_event(OrderAccepted).event_type == "ORDER_ACCEPTED"


def test_accepted_carries_venue_and_execution_ids(make_event):
    event = make_event(
        OrderAccepted,
        venue_order_id="VENUE-000001",
        execution_request_id="EXREQ-20260813-000001",
    )
    assert event.venue_order_id == "VENUE-000001"
    assert event.execution_request_id == "EXREQ-20260813-000001"


def test_accepted_event_is_immutable_after_creation(make_event):
    # Spec #24: a produced event is a fact - the venue id can never be edited;
    # a new fact means a NEW event, never a modified one.
    event = make_event(OrderAccepted, venue_order_id="VENUE-000001")
    with pytest.raises(dataclasses.FrozenInstanceError):
        event.venue_order_id = "VENUE-000002"
