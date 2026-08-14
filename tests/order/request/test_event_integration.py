"""Integration tests: OrderRequestService + Event Factory + Outbox + Publisher.

Covers the Commit 32 Part 1.4 pipeline:

    Create -> State Transition -> Event Factory -> Outbox -> Commit
    -> Publisher -> Event Bus
"""

import pytest

from services.order.request.errors import OrderRequestValidationError
from services.order.request.event_publisher import (
    EventBusUnavailable,
    OrderRequestEventPublisher,
    OrderRequestOutbox,
)
from services.order.request.event_types import OrderRequestEventType
from services.order.request.events import OrderRequestEvent, OutboxStatus
from services.order.request.lifecycle import InvalidStateTransition
from services.order.request.service import OrderRequestService
from services.order.request.state import OrderRequestState
from services.risk.authorization.integration import AuthorizedExecutionContext


def valid_context(**overrides) -> AuthorizedExecutionContext:
    defaults = dict(
        intent_id="INT-001",
        authorization_id="AUTH-001",
        certificate_id="CERT-001",
        decision_id="RISK-001",
        correlation_id="CORR-001",
        strategy_id="STRAT-001",
        session_id="SESSION-001",
        signal_id="SIG-001",
        symbol="NVDA",
        side="BUY",
        approved_quantity=100.0,
    )
    defaults.update(overrides)
    return AuthorizedExecutionContext(**defaults)


@pytest.fixture
def outbox() -> OrderRequestOutbox:
    return OrderRequestOutbox()


@pytest.fixture
def publisher() -> OrderRequestEventPublisher:
    return OrderRequestEventPublisher()


@pytest.fixture
def service(publisher, outbox) -> OrderRequestService:
    return OrderRequestService(publisher=publisher, outbox=outbox)


def create_request(service, *, created_at=1000.0, **context_overrides):
    return service.create(
        valid_context(**context_overrides),
        order_type="LIMIT",
        time_in_force="DAY",
        limit_price=180.0,
        created_at=created_at,
    )


def advance_to_submitted(service, request_id, *, base_timestamp=1000.0):
    service.validate(request_id, timestamp=base_timestamp + 1)
    service.normalize(request_id, timestamp=base_timestamp + 2)
    service.submit(request_id, timestamp=base_timestamp + 3)


# --- event emission -----------------------------------------------------------


def test_create_emits_created_event(service):
    request = create_request(service)
    events = service.get_events(request.order_request_id)
    assert len(events) == 1
    event = events[0]
    assert event.event_type == OrderRequestEventType.ORDER_REQUEST_CREATED
    assert event.sequence == 1
    assert event.state == OrderRequestState.CREATED
    assert event.aggregate_id == request.order_request_id
    assert event.causation_id is None


def test_full_happy_path_emits_six_events(service):
    request = create_request(service)
    request_id = request.order_request_id

    service.validate(request_id, timestamp=1001)
    service.normalize(request_id, timestamp=1002)
    service.submit(request_id, timestamp=1003)
    service.accept(request_id, timestamp=1004)
    service.handoff(request_id, timestamp=1005)

    events = service.get_events(request_id)
    assert [event.sequence for event in events] == [1, 2, 3, 4, 5, 6]
    assert [event.event_type for event in events] == [
        OrderRequestEventType.ORDER_REQUEST_CREATED,
        OrderRequestEventType.ORDER_REQUEST_VALIDATED,
        OrderRequestEventType.ORDER_REQUEST_NORMALIZED,
        OrderRequestEventType.ORDER_REQUEST_SUBMITTED,
        OrderRequestEventType.ORDER_REQUEST_ACCEPTED,
        OrderRequestEventType.ORDER_REQUEST_HANDOFF,
    ]
    assert [event.state for event in events] == [
        OrderRequestState.CREATED,
        OrderRequestState.VALIDATED,
        OrderRequestState.NORMALIZED,
        OrderRequestState.SUBMITTED,
        OrderRequestState.ACCEPTED,
        OrderRequestState.HANDOFF,
    ]
    assert service.get_state(request_id) == OrderRequestState.HANDOFF


def test_event_sequence_is_monotonic(service):
    request = create_request(service)
    request_id = request.order_request_id
    service.validate(request_id, timestamp=1001)
    service.normalize(request_id, timestamp=1002)
    service.submit(request_id, timestamp=1003)
    service.accept(request_id, timestamp=1004)
    service.handoff(request_id, timestamp=1005)

    sequences = [event.sequence for event in service.get_events(request_id)]
    assert sequences == sorted(sequences)
    assert sequences == list(range(1, len(sequences) + 1))


def test_causation_chain_links_all_events(service):
    request = create_request(service)
    request_id = request.order_request_id
    service.validate(request_id, timestamp=1001)
    service.normalize(request_id, timestamp=1002)
    service.submit(request_id, timestamp=1003)

    events = service.get_events(request_id)
    assert events[0].causation_id is None
    for previous, current in zip(events, events[1:]):
        assert current.causation_id == previous.event_id


def test_events_carry_correlation_id(service):
    request = create_request(service)
    request_id = request.order_request_id
    advance_to_submitted(service, request_id)

    for event in service.get_events(request_id):
        assert event.correlation_id == request.correlation_id


def test_event_ids_are_unique_across_aggregates(service):
    # Part 1.5 idempotent create: the second request must come from a
    # different authorization (different idempotency key) to be a new aggregate.
    first = create_request(service, created_at=1000)
    second = create_request(service, created_at=2000, session_id="SESSION-002")
    first_ids = {event.event_id for event in service.get_events(first.order_request_id)}
    second_ids = {event.event_id for event in service.get_events(second.order_request_id)}
    assert first_ids.isdisjoint(second_ids)


def test_sequences_are_aggregate_local(service):
    first = create_request(service, created_at=1000)
    second = create_request(service, created_at=2000, session_id="SESSION-002")
    first_sequences = [e.sequence for e in service.get_events(first.order_request_id)]
    second_sequences = [e.sequence for e in service.get_events(second.order_request_id)]
    # Both aggregates legitimately start their own sequence at 1.
    assert first_sequences == [1]
    assert second_sequences == [1]


def test_events_are_append_only(service):
    request = create_request(service)
    request_id = request.order_request_id
    service.validate(request_id, timestamp=1001)
    events_before = service.get_events(request_id)
    assert len(events_before) == 2
    # The immutable event objects must not change after they were recorded.
    assert events_before[0].sequence == 1
    assert events_before[0].state == OrderRequestState.CREATED


def test_state_transition_history_recorded(service):
    request = create_request(service)
    request_id = request.order_request_id
    service.validate(request_id, timestamp=1001)
    history = service.get_history(request_id)
    assert len(history) == 1
    assert history[0].from_state == OrderRequestState.CREATED
    assert history[0].to_state == OrderRequestState.VALIDATED


# --- terminal paths ------------------------------------------------------------


def test_rejected_event_payload_contains_reason(service):
    request = create_request(service)
    request_id = request.order_request_id
    advance_to_submitted(service, request_id)
    service.reject(request_id, timestamp=1004, reason="VENUE_UNAVAILABLE")

    assert service.get_state(request_id) == OrderRequestState.REJECTED
    rejected = service.get_events(request_id)[-1]
    assert rejected.event_type == OrderRequestEventType.ORDER_REQUEST_REJECTED
    assert rejected.payload["reason"] == "VENUE_UNAVAILABLE"


def test_reject_requires_reason(service):
    request = create_request(service)
    request_id = request.order_request_id
    advance_to_submitted(service, request_id)
    with pytest.raises(ValueError, match="reason"):
        service.reject(request_id, timestamp=1004, reason="")


def test_cancel_from_created_is_legal(service):
    request = create_request(service)
    service.cancel(request.order_request_id, timestamp=1001, reason="USER_REQUEST")
    assert service.get_state(request.order_request_id) == OrderRequestState.CANCELLED
    cancelled = service.get_events(request.order_request_id)[-1]
    assert cancelled.event_type == OrderRequestEventType.ORDER_REQUEST_CANCELLED
    assert cancelled.payload["reason"] == "USER_REQUEST"


def test_expire_from_validated_is_legal(service):
    request = create_request(service)
    request_id = request.order_request_id
    service.validate(request_id, timestamp=1001)
    service.expire(request_id, timestamp=1002, reason="TIF_EXPIRED")
    assert service.get_state(request_id) == OrderRequestState.EXPIRED
    assert service.get_events(request_id)[-1].event_type == (
        OrderRequestEventType.ORDER_REQUEST_EXPIRED
    )


def test_terminal_state_cannot_transition(service):
    request = create_request(service)
    request_id = request.order_request_id
    service.cancel(request_id, timestamp=1001)
    with pytest.raises(InvalidStateTransition):
        service.validate(request_id, timestamp=1002)


# --- lifecycle guards -----------------------------------------------------------


def test_illegal_transition_raises(service):
    request = create_request(service)
    request_id = request.order_request_id
    # SUBMITTED is only reachable from NORMALIZED; accept is only legal from
    # SUBMITTED.
    with pytest.raises(InvalidStateTransition):
        service.accept(request_id, timestamp=1001)
    assert service.get_state(request_id) == OrderRequestState.CREATED


def test_validation_failure_blocks_transition(service):
    request = service.create(
        valid_context(symbol="NV DA"),  # invalid symbol: cannot be auto-repaired
        order_type="LIMIT",
        time_in_force="DAY",
        limit_price=180.0,
        created_at=1000,
    )
    with pytest.raises(OrderRequestValidationError):
        service.validate(request.order_request_id, timestamp=1001)
    # State must stay CREATED: the transition never happened.
    assert service.get_state(request.order_request_id) == OrderRequestState.CREATED


def test_idempotent_noop_does_not_emit_duplicate_event(service):
    request = create_request(service)
    request_id = request.order_request_id
    advance_to_submitted(service, request_id)
    events_after_first_submit = service.get_events(request_id)
    assert events_after_first_submit[-1].event_type == (
        OrderRequestEventType.ORDER_REQUEST_SUBMITTED
    )

    service.submit(request_id, timestamp=2000)
    events_after_second_submit = service.get_events(request_id)
    assert len(events_after_second_submit) == len(events_after_first_submit)


# --- outbox reliability ----------------------------------------------------------


def test_event_is_stored_in_outbox(service, outbox):
    request = create_request(service)
    request_id = request.order_request_id
    advance_to_submitted(service, request_id)

    record = outbox.get(service.get_events(request_id)[-1].event_id)
    assert record is not None
    assert record.event_type == OrderRequestEventType.ORDER_REQUEST_SUBMITTED
    assert record.status == OutboxStatus.PUBLISHED


def test_event_bus_failure_keeps_outbox(service, publisher, outbox):
    request = create_request(service)
    request_id = request.order_request_id
    service.validate(request_id, timestamp=1001)
    service.normalize(request_id, timestamp=1002)

    publisher.fail = True
    service.submit(request_id, timestamp=1003)

    submitted_event = service.get_events(request_id)[-1]
    record = outbox.get(submitted_event.event_id)
    assert record.status == OutboxStatus.PENDING
    assert record.event_type == OrderRequestEventType.ORDER_REQUEST_SUBMITTED
    # The state change still happened: state and event are one atomic fact.
    assert service.get_state(request_id) == OrderRequestState.SUBMITTED


def test_published_records_are_marked_published(service, outbox):
    request = create_request(service)
    assert outbox.get(service.get_events(request.order_request_id)[0].event_id).status == (
        OutboxStatus.PUBLISHED
    )
    assert outbox.get_pending() == []


def test_retry_after_bus_recovery(service, publisher, outbox):
    request = create_request(service)
    request_id = request.order_request_id
    service.validate(request_id, timestamp=1001)
    service.normalize(request_id, timestamp=1002)

    publisher.fail = True
    service.submit(request_id, timestamp=1003)
    assert len(outbox.get_pending()) == 1

    # Bus recovers: the relay retries the PENDING records.
    publisher.fail = False
    published = service.publish_pending()

    assert published == 1
    assert outbox.get_pending() == []
    submitted_event = service.get_events(request_id)[-1]
    assert outbox.get(submitted_event.event_id).status == OutboxStatus.PUBLISHED
    assert submitted_event.event_id in publisher.published_event_ids()


def test_all_events_eventually_reach_the_bus(service, publisher, outbox):
    request = create_request(service)
    request_id = request.order_request_id

    publisher.fail = True
    service.validate(request_id, timestamp=1001)
    service.normalize(request_id, timestamp=1002)
    service.submit(request_id, timestamp=1003)
    assert len(outbox.get_pending()) == 3

    publisher.fail = False
    service.publish_pending()

    assert len(publisher.bus.events) == 4  # CREATED + 3 retried events


def test_publish_failure_is_retryable_not_fatal(publisher):
    # An event that has never been delivered raises; the outbox keeps it
    # PENDING and a later retry succeeds (covered by test_retry_after_bus_recovery).
    unpublished = OrderRequestEvent(
        event_id="EVT-UNPUBLISHED",
        event_type=OrderRequestEventType.ORDER_REQUEST_SUBMITTED,
        aggregate_id="OR-001",
        aggregate_type="OrderRequest",
        correlation_id="CORR-001",
        causation_id="EVT-001",
        sequence=4,
        timestamp=1003.0,
        state=OrderRequestState.SUBMITTED,
        payload={"order_request_id": "OR-001"},
    )
    publisher.fail = True
    with pytest.raises(EventBusUnavailable):
        publisher.publish(unpublished)
    assert publisher.published_count("EVT-UNPUBLISHED") == 0
