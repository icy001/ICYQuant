"""Tests for the order request event model (Commit 32 Part 1.4)."""

import pytest

from services.order.request.event_types import OrderRequestEventType
from services.order.request.events import (
    OrderRequestEvent,
    OutboxRecord,
    OutboxStatus,
)
from services.order.request.state import OrderRequestState


def make_event(
    event_id: str = "EVT-001",
    *,
    event_type: OrderRequestEventType = OrderRequestEventType.ORDER_REQUEST_CREATED,
    aggregate_id: str = "OR-001",
    aggregate_type: str = "OrderRequest",
    correlation_id: str = "CORR-001",
    causation_id=None,
    sequence: int = 1,
    timestamp: float = 1000.0,
    state: OrderRequestState = OrderRequestState.CREATED,
    payload=None,
) -> OrderRequestEvent:
    return OrderRequestEvent(
        event_id=event_id,
        event_type=event_type,
        aggregate_id=aggregate_id,
        aggregate_type=aggregate_type,
        correlation_id=correlation_id,
        causation_id=causation_id,
        sequence=sequence,
        timestamp=timestamp,
        state=state,
        payload=payload if payload is not None else {"order_request_id": aggregate_id},
    )


def test_event_type_has_nine_explicit_values():
    expected = {
        "ORDER_REQUEST_CREATED",
        "ORDER_REQUEST_VALIDATED",
        "ORDER_REQUEST_NORMALIZED",
        "ORDER_REQUEST_SUBMITTED",
        "ORDER_REQUEST_ACCEPTED",
        "ORDER_REQUEST_REJECTED",
        "ORDER_REQUEST_CANCELLED",
        "ORDER_REQUEST_EXPIRED",
        "ORDER_REQUEST_HANDOFF",
    }
    assert {member.value for member in OrderRequestEventType} == expected


def test_event_type_is_str_enum():
    assert OrderRequestEventType.ORDER_REQUEST_CREATED == "ORDER_REQUEST_CREATED"
    assert OrderRequestEventType.ORDER_REQUEST_SUBMITTED == "ORDER_REQUEST_SUBMITTED"


def test_no_generic_updated_event():
    values = {member.value for member in OrderRequestEventType}
    assert "ORDER_REQUEST_UPDATED" not in values


def test_event_carries_aggregate_identity():
    event = make_event()
    assert event.aggregate_type == "OrderRequest"
    assert event.aggregate_id == "OR-001"


def test_event_id_differs_from_aggregate_id():
    event = make_event(event_id="EVT-001", aggregate_id="OR-001")
    assert event.event_id != event.aggregate_id


def test_event_is_frozen():
    event = make_event()
    with pytest.raises(AttributeError):
        event.sequence = 99  # type: ignore[misc]


def test_event_is_immutable_and_identified_by_event_id():
    event = make_event()
    # A frozen dataclass carrying a dict payload is not hashable; the event is
    # identified by its unique event_id instead.
    assert event.sequence == 1
    assert event.causation_id is None
    with pytest.raises(AttributeError):
        event.payload = {}  # type: ignore[misc]


def test_event_state_after_application():
    event = make_event(
        event_type=OrderRequestEventType.ORDER_REQUEST_SUBMITTED,
        state=OrderRequestState.SUBMITTED,
    )
    assert event.state == OrderRequestState.SUBMITTED


def test_event_as_dict_round_trip():
    event = make_event(
        event_type=OrderRequestEventType.ORDER_REQUEST_REJECTED,
        state=OrderRequestState.REJECTED,
        payload={"order_request_id": "OR-001", "reason": "VENUE_UNAVAILABLE"},
    )
    as_dict = event.as_dict()
    assert as_dict["event_id"] == "EVT-001"
    assert as_dict["event_type"] == "ORDER_REQUEST_REJECTED"
    assert as_dict["aggregate_type"] == "OrderRequest"
    assert as_dict["state"] == "REJECTED"
    assert as_dict["payload"]["reason"] == "VENUE_UNAVAILABLE"
    assert as_dict["causation_id"] is None


def test_event_payload_is_copied_in_as_dict():
    event = make_event(payload={"order_request_id": "OR-001"})
    as_dict = event.as_dict()
    as_dict["payload"]["order_request_id"] = "MUTATED"
    assert event.payload["order_request_id"] == "OR-001"


# --- OutboxRecord ----------------------------------------------------------


def test_outbox_status_values_are_stable():
    assert OutboxStatus.PENDING == "PENDING"
    assert OutboxStatus.PUBLISHED == "PUBLISHED"
    assert OutboxStatus.FAILED == "FAILED"


def test_outbox_record_from_event_is_pending():
    event = make_event(
        event_type=OrderRequestEventType.ORDER_REQUEST_SUBMITTED,
        sequence=4,
        timestamp=1000.0,
    )
    record = OutboxRecord.from_event(event)
    assert record.event_id == event.event_id
    assert record.aggregate_id == event.aggregate_id
    assert record.event_type == event.event_type
    assert record.sequence == 4
    assert record.created_at == 1000.0
    assert record.published_at is None
    assert record.status == OutboxStatus.PENDING


def test_outbox_record_mark_published():
    record = OutboxRecord.from_event(make_event())
    published = record.mark_published(published_at=1001.0)
    assert published.status == OutboxStatus.PUBLISHED
    assert published.published_at == 1001.0
    # Original record is unchanged (immutable / append-only).
    assert record.status == OutboxStatus.PENDING
    assert record.published_at is None


def test_outbox_record_mark_failed():
    record = OutboxRecord.from_event(make_event())
    failed = record.mark_failed()
    assert failed.status == OutboxStatus.FAILED


def test_outbox_record_payload_does_not_alias_event_payload():
    event = make_event(payload={"order_request_id": "OR-001"})
    record = OutboxRecord.from_event(event)
    record.payload["order_request_id"] = "MUTATED"
    assert event.payload["order_request_id"] == "OR-001"
