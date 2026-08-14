"""Tests for the order event base model (Commit 33 Part 1.4 #3-#9)."""

from __future__ import annotations

import dataclasses

import pytest

from services.order.domain.events import OrderCreated, OrderEvent


def test_event_is_frozen(make_event):
    with pytest.raises(dataclasses.FrozenInstanceError):
        make_event().order_id = "OTHER"


def test_event_identity_is_distinct_from_order_id(make_event):
    event = make_event(
        event_id="EVT-ORD-000042",
        order_id="ORD-20260813-000001",
    )
    assert event.event_id == "EVT-ORD-000042"
    assert event.event_id != event.order_id


def test_aggregate_identity_is_the_order(make_event):
    event = make_event(aggregate_id="ORD-20260813-000001")
    assert event.aggregate_type == "ORDER"
    assert event.aggregate_id == event.order_id


def test_correlation_and_causation_chain(make_event):
    event = make_event(causation_id="CMD-001")
    assert event.correlation_id == "CORR-001"
    assert event.causation_id == "CMD-001"
    assert make_event().causation_id is None


def test_payload_version_defaults_to_one(make_event):
    assert make_event().payload_version == 1


def test_sequence_starts_at_one(make_event):
    assert make_event(sequence=1).sequence == 1


def test_event_type_must_match_the_concrete_class(make_event):
    with pytest.raises(ValueError, match="event_type"):
        make_event(OrderCreated, event_type="ORDER_ACCEPTED")


def test_required_identity_fields_are_enforced(make_event):
    with pytest.raises(ValueError, match="event_id"):
        make_event(event_id="")
    with pytest.raises(ValueError, match="correlation_id"):
        make_event(correlation_id="")
    with pytest.raises(ValueError, match="order_request_id"):
        make_event(order_request_id="")
    with pytest.raises(ValueError, match="aggregate_id"):
        make_event(aggregate_id="")


def test_occurred_at_is_required(make_event):
    with pytest.raises(ValueError, match="occurred_at"):
        make_event(occurred_at=None)


def test_sequence_must_be_positive(make_event):
    with pytest.raises(ValueError, match="sequence"):
        make_event(sequence=0)
    with pytest.raises(ValueError, match="sequence"):
        make_event(sequence=-1)


def test_new_fact_is_a_new_event_never_a_mutation(make_event):
    first = make_event(event_id="EVT-ORD-000001", sequence=1)
    second = make_event(event_id="EVT-ORD-000002", sequence=2)
    assert first.sequence == 1
    assert second.sequence == 2
    assert first.event_id != second.event_id


def test_base_event_can_record_a_generic_event(make_event):
    event = make_event(OrderEvent)
    assert isinstance(event, OrderEvent)
    assert event.event_type == "ORDER_EVENT"
