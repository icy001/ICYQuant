"""StoredEvent model tests (Commit 34 Part 1.1 #2 / #9 / #11)."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest


def test_stored_event_fields(make_stored_event):
    event = make_stored_event()
    assert event.event_id == "EVT-ORD-000001"
    assert event.aggregate_id == "ORD-001"
    assert event.aggregate_type == "ORDER"
    assert event.aggregate_version == 1
    assert event.event_type == "ORDER_CREATED"


def test_stored_event_identity(make_stored_event):
    event = make_stored_event(event_id="EVT-ORD-000099")
    assert event.event_id == "EVT-ORD-000099"


def test_stored_event_is_immutable(make_stored_event):
    event = make_stored_event()
    with pytest.raises(FrozenInstanceError):
        event.aggregate_version = 10  # type: ignore[misc]


def test_stored_event_requires_event_id(make_stored_event):
    with pytest.raises(ValueError):
        make_stored_event(event_id="")


def test_stored_event_requires_aggregate_version(make_stored_event):
    with pytest.raises(ValueError):
        make_stored_event(version=0)


def test_stored_event_requires_event_type(make_stored_event):
    with pytest.raises(ValueError):
        make_stored_event(event_type="")


def test_stored_event_keeps_payload(make_stored_event):
    event = make_stored_event(payload={"venue_order_id": "VENUE-000001"})
    assert event.payload == {"venue_order_id": "VENUE-000001"}
