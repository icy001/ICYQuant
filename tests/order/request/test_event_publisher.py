"""Tests for the event publisher, event bus and outbox (Commit 32 Part 1.4)."""

import pytest

from services.order.request.event_publisher import (
    EventBusUnavailable,
    InMemoryEventBus,
    OrderRequestEventPublisher,
    OrderRequestOutbox,
)
from services.order.request.event_types import OrderRequestEventType
from services.order.request.events import OrderRequestEvent
from services.order.request.events import OutboxStatus
from services.order.request.state import OrderRequestState


def make_event(
    event_id: str = "EVT-001",
    *,
    event_type: OrderRequestEventType = OrderRequestEventType.ORDER_REQUEST_SUBMITTED,
    aggregate_id: str = "OR-001",
    sequence: int = 4,
    timestamp: float = 1000.0,
) -> OrderRequestEvent:
    return OrderRequestEvent(
        event_id=event_id,
        event_type=event_type,
        aggregate_id=aggregate_id,
        aggregate_type="OrderRequest",
        correlation_id="CORR-001",
        causation_id="EVT-003",
        sequence=sequence,
        timestamp=timestamp,
        state=OrderRequestState.SUBMITTED,
        payload={"order_request_id": aggregate_id},
    )


@pytest.fixture
def bus() -> InMemoryEventBus:
    return InMemoryEventBus()


@pytest.fixture
def publisher(bus) -> OrderRequestEventPublisher:
    return OrderRequestEventPublisher(bus=bus)


@pytest.fixture
def outbox() -> OrderRequestOutbox:
    return OrderRequestOutbox()


# --- publisher / event bus -------------------------------------------------


def test_publish_delivers_to_bus(publisher, bus):
    event = make_event()
    publisher.publish(event)
    assert bus.events == [event]


def test_duplicate_event_is_idempotent(publisher, bus):
    event = make_event(event_id="EVT-001")
    publisher.publish(event)
    publisher.publish(event)
    assert publisher.published_count("EVT-001") == 1
    assert len(bus.events) == 1


def test_published_count_unknown_event_is_zero(publisher):
    assert publisher.published_count("EVT-NOPE") == 0


def test_bus_failure_raises(publisher):
    publisher.fail = True
    with pytest.raises(EventBusUnavailable):
        publisher.publish(make_event())


def test_bus_failure_does_not_mark_published(publisher):
    publisher.fail = True
    with pytest.raises(EventBusUnavailable):
        publisher.publish(make_event(event_id="EVT-001"))
    assert publisher.published_count("EVT-001") == 0


def test_publish_after_recovery(publisher, bus):
    publisher.fail = True
    with pytest.raises(EventBusUnavailable):
        publisher.publish(make_event(event_id="EVT-001"))
    publisher.fail = False
    publisher.publish(make_event(event_id="EVT-001"))
    assert publisher.published_count("EVT-001") == 1
    assert len(bus.events) == 1


def test_publisher_does_not_reorder(publisher, bus):
    for index in range(1, 4):
        publisher.publish(
            make_event(event_id=f"EVT-00{index}", sequence=index)
        )
    assert [event.sequence for event in bus.events] == [1, 2, 3]


def test_in_memory_bus_subscribers_receive_events(bus):
    received = []
    bus.subscribe(received.append)
    publisher = OrderRequestEventPublisher(bus=bus)
    event = make_event(event_id="EVT-001")
    publisher.publish(event)
    assert received == [event]


# --- outbox ------------------------------------------------------------------


def test_outbox_append_creates_pending_record(outbox):
    event = make_event(
        event_type=OrderRequestEventType.ORDER_REQUEST_SUBMITTED,
        sequence=4,
    )
    record = outbox.append(event)
    assert record.event_id == "EVT-001"
    assert record.aggregate_id == "OR-001"
    assert record.event_type == OrderRequestEventType.ORDER_REQUEST_SUBMITTED
    assert record.sequence == 4
    assert record.status == OutboxStatus.PENDING
    assert record.published_at is None


def test_outbox_append_is_idempotent_by_event_id(outbox):
    event = make_event(event_id="EVT-001")
    first = outbox.append(event)
    second = outbox.append(event)
    assert first is second
    assert len(outbox.all()) == 1


def test_outbox_mark_published(outbox):
    event = make_event(event_id="EVT-001")
    outbox.append(event)
    record = outbox.mark_published("EVT-001", published_at=1001.0)
    assert record.status == OutboxStatus.PUBLISHED
    assert record.published_at == 1001.0
    assert outbox.get("EVT-001").status == OutboxStatus.PUBLISHED


def test_outbox_mark_failed(outbox):
    outbox.append(make_event(event_id="EVT-001"))
    record = outbox.mark_failed("EVT-001")
    assert record.status == OutboxStatus.FAILED


def test_outbox_mark_unknown_raises(outbox):
    with pytest.raises(KeyError):
        outbox.mark_published("EVT-NOPE")


def test_outbox_get_unknown_returns_none(outbox):
    assert outbox.get("EVT-NOPE") is None


def test_outbox_get_pending_filters(outbox):
    outbox.append(make_event(event_id="EVT-001"))
    outbox.append(make_event(event_id="EVT-002"))
    outbox.mark_published("EVT-001")
    pending = outbox.get_pending()
    assert [record.event_id for record in pending] == ["EVT-002"]


def test_outbox_get_failed_filters(outbox):
    outbox.append(make_event(event_id="EVT-001"))
    outbox.mark_failed("EVT-001")
    failed = outbox.get_failed()
    assert [record.event_id for record in failed] == ["EVT-001"]
    assert outbox.get_pending() == []
