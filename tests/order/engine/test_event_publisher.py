"""Tests for the event publisher boundary (Commit 33 Part 1.4 #18/#19/#26)."""

from __future__ import annotations

from datetime import datetime

import pytest

from services.order.domain.events import OrderAccepted, OrderCreated, OrderEvent
from services.order.engine.event_publisher import (
    EventPublishError,
    InMemoryEventPublisher,
    OrderEventPublisher,
)

TS = datetime(2026, 8, 13, 9, 30, 0)


def _make_event(cls=OrderCreated, **overrides) -> OrderEvent:
    defaults = dict(
        event_id="EVT-ORD-000001",
        aggregate_id="ORD-20260813-000001",
        aggregate_type="ORDER",
        order_id="ORD-20260813-000001",
        order_request_id="OR-20260813-000001",
        correlation_id="CORR-001",
        causation_id=None,
        occurred_at=TS,
        sequence=1,
        payload_version=1,
    )
    defaults.update(overrides)
    return cls(**defaults)


def test_in_memory_publisher_satisfies_the_protocol():
    # The order engine only depends on the protocol; the bus impl is swappable.
    assert isinstance(InMemoryEventPublisher(), OrderEventPublisher)


def test_publish_records_events_in_order():
    publisher = InMemoryEventPublisher()
    first = _make_event(OrderCreated, event_id="EVT-ORD-000001", sequence=1)
    second = _make_event(
        OrderAccepted,
        event_id="EVT-ORD-000002",
        sequence=2,
        venue_order_id="VENUE-000001",
    )

    publisher.publish(first)
    publisher.publish(second)

    assert publisher.events == [first, second]


def test_published_filters_by_event_type():
    publisher = InMemoryEventPublisher()
    publisher.publish(_make_event(OrderCreated, event_id="EVT-ORD-000001", sequence=1))
    publisher.publish(_make_event(OrderAccepted, event_id="EVT-ORD-000002", sequence=2))

    assert len(publisher.published("ORDER_CREATED")) == 1
    assert len(publisher.published("ORDER_ACCEPTED")) == 1
    assert publisher.published("ORDER_REJECTED") == []
    assert len(publisher.published()) == 2


def test_events_property_returns_a_copy():
    publisher = InMemoryEventPublisher()
    publisher.publish(_make_event())
    publisher.events.append(_make_event(event_id="EVT-ORD-999999"))
    assert len(publisher.events) == 1


def test_publish_failure_raises_and_never_pretends_delivery():
    # Fail-closed: a delivery failure raises; nothing is recorded as published.
    publisher = InMemoryEventPublisher()
    publisher.fail_on_publish = True

    with pytest.raises(EventPublishError):
        publisher.publish(_make_event())

    assert publisher.events == []
