"""Tests for the order request event factory (Commit 32 Part 1.4)."""

import itertools

import pytest

from services.order.request.event_factory import (
    AGGREGATE_TYPE,
    OrderRequestEventFactory,
    new_event_id,
)
from services.order.request.event_types import OrderRequestEventType
from services.order.request.factory import OrderRequestFactory
from services.order.request.model import OrderRequest
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
def order_request():
    factory = OrderRequestFactory()
    return factory.create(
        valid_context(),
        order_type="LIMIT",
        time_in_force="DAY",
        limit_price=180.0,
        created_at=1000,
    )


@pytest.fixture
def event_factory() -> OrderRequestEventFactory:
    return OrderRequestEventFactory()


def test_event_factory_creates_event(order_request, event_factory):
    event = event_factory.create(
        order_request,
        OrderRequestEventType.ORDER_REQUEST_CREATED,
        sequence=1,
        causation_id=None,
        timestamp=1000,
    )
    assert event.aggregate_id == order_request.order_request_id
    assert event.sequence == 1
    assert event.event_type == OrderRequestEventType.ORDER_REQUEST_CREATED
    assert event.aggregate_type == AGGREGATE_TYPE
    assert event.correlation_id == order_request.correlation_id


def test_event_causation_chain(order_request, event_factory):
    created = event_factory.create(
        order_request,
        OrderRequestEventType.ORDER_REQUEST_CREATED,
        sequence=1,
        causation_id=None,
        timestamp=1000,
    )
    validated = event_factory.create(
        order_request,
        OrderRequestEventType.ORDER_REQUEST_VALIDATED,
        sequence=2,
        causation_id=created.event_id,
        timestamp=1001,
    )
    assert validated.causation_id == created.event_id


def test_event_id_is_unique_per_event(order_request, event_factory):
    first = event_factory.create(
        order_request,
        OrderRequestEventType.ORDER_REQUEST_CREATED,
        sequence=1,
        causation_id=None,
        timestamp=1000,
    )
    second = event_factory.create(
        order_request,
        OrderRequestEventType.ORDER_REQUEST_VALIDATED,
        sequence=2,
        causation_id=first.event_id,
        timestamp=1001,
    )
    assert first.event_id != second.event_id
    assert first.event_id != order_request.order_request_id


def test_event_id_shape(order_request, event_factory):
    event = event_factory.create(
        order_request,
        OrderRequestEventType.ORDER_REQUEST_CREATED,
        sequence=1,
        causation_id=None,
        timestamp=1000,
    )
    assert event.event_id.startswith("EVT-")


def test_new_event_id_is_monotonic():
    first = new_event_id()
    second = new_event_id()
    assert first != second


def test_event_state_maps_from_event_type(order_request, event_factory):
    mapping = {
        OrderRequestEventType.ORDER_REQUEST_CREATED: OrderRequestState.CREATED,
        OrderRequestEventType.ORDER_REQUEST_VALIDATED: OrderRequestState.VALIDATED,
        OrderRequestEventType.ORDER_REQUEST_NORMALIZED: OrderRequestState.NORMALIZED,
        OrderRequestEventType.ORDER_REQUEST_SUBMITTED: OrderRequestState.SUBMITTED,
        OrderRequestEventType.ORDER_REQUEST_ACCEPTED: OrderRequestState.ACCEPTED,
        OrderRequestEventType.ORDER_REQUEST_REJECTED: OrderRequestState.REJECTED,
        OrderRequestEventType.ORDER_REQUEST_CANCELLED: OrderRequestState.CANCELLED,
        OrderRequestEventType.ORDER_REQUEST_EXPIRED: OrderRequestState.EXPIRED,
        OrderRequestEventType.ORDER_REQUEST_HANDOFF: OrderRequestState.HANDOFF,
    }
    for event_type, state in mapping.items():
        event = event_factory.create(
            order_request,
            event_type,
            sequence=1,
            causation_id=None,
            timestamp=1000,
        )
        assert event.state == state


def test_payload_has_minimal_business_facts(order_request, event_factory):
    event = event_factory.create(
        order_request,
        OrderRequestEventType.ORDER_REQUEST_SUBMITTED,
        sequence=4,
        causation_id="EVT-003",
        timestamp=1004,
    )
    payload = event.payload
    assert payload["order_request_id"] == order_request.order_request_id
    assert payload["symbol"] == "NVDA"
    assert payload["side"] == "BUY"
    assert payload["quantity"] == 100
    assert payload["order_type"] == "LIMIT"
    assert payload["limit_price"] == 180.0


def test_payload_keeps_lineage_and_correlation(order_request, event_factory):
    event = event_factory.create(
        order_request,
        OrderRequestEventType.ORDER_REQUEST_CREATED,
        sequence=1,
        causation_id=None,
        timestamp=1000,
    )
    payload = event.payload
    assert payload["correlation_id"] == "CORR-001"
    assert payload["intent_id"] == "INT-001"
    assert payload["authorization_id"] == "AUTH-001"
    assert payload["certificate_id"] == "CERT-001"
    assert payload["decision_id"] == "RISK-001"


def test_payload_does_not_copy_system_state(order_request, event_factory):
    event = event_factory.create(
        order_request,
        OrderRequestEventType.ORDER_REQUEST_SUBMITTED,
        sequence=4,
        causation_id="EVT-003",
        timestamp=1004,
    )
    payload_keys = set(event.payload.keys())
    # The payload carries facts, never an embedded copy of other systems.
    assert "positions" not in payload_keys
    assert "account" not in payload_keys
    assert "portfolio" not in payload_keys


def test_rejected_event_payload_contains_reason(order_request, event_factory):
    event = event_factory.create(
        order_request,
        OrderRequestEventType.ORDER_REQUEST_REJECTED,
        sequence=5,
        causation_id="EVT-004",
        timestamp=1005,
        reason="VENUE_UNAVAILABLE",
    )
    assert event.payload["reason"] == "VENUE_UNAVAILABLE"


def test_non_terminal_event_without_reason_has_no_reason_key(order_request, event_factory):
    event = event_factory.create(
        order_request,
        OrderRequestEventType.ORDER_REQUEST_VALIDATED,
        sequence=2,
        causation_id="EVT-001",
        timestamp=1001,
    )
    assert "reason" not in event.payload


def test_sequence_must_be_positive(order_request, event_factory):
    with pytest.raises(ValueError, match="sequence"):
        event_factory.create(
            order_request,
            OrderRequestEventType.ORDER_REQUEST_CREATED,
            sequence=0,
            causation_id=None,
            timestamp=1000,
        )


def test_empty_request_id_rejected(event_factory):
    empty = OrderRequest(
        order_request_id="",
        intent_id="INT-001",
        authorization_id="AUTH-001",
        certificate_id="CERT-001",
        decision_id="RISK-001",
        strategy_id="STRAT-001",
        session_id="SESSION-001",
        signal_id="SIG-001",
        correlation_id="CORR-001",
        symbol="NVDA",
        side="BUY",
        quantity=100.0,
        order_type="MARKET",
        time_in_force="DAY",
        limit_price=None,
        created_at=1000,
        idempotency_key="STRAT-001:SESSION-001:INT-001",
    )
    with pytest.raises(ValueError, match="order_request_id"):
        event_factory.create(
            empty,
            OrderRequestEventType.ORDER_REQUEST_CREATED,
            sequence=1,
            causation_id=None,
            timestamp=1000,
        )


def test_factory_supports_injectable_event_id_generator(order_request):
    generator = itertools.count(1)
    factory = OrderRequestEventFactory(event_id_generator=lambda: f"EVT-FIXED-{next(generator):03d}")
    first = factory.create(
        order_request,
        OrderRequestEventType.ORDER_REQUEST_CREATED,
        sequence=1,
        causation_id=None,
        timestamp=1000,
    )
    second = factory.create(
        order_request,
        OrderRequestEventType.ORDER_REQUEST_VALIDATED,
        sequence=2,
        causation_id=first.event_id,
        timestamp=1001,
    )
    assert first.event_id == "EVT-FIXED-001"
    assert second.event_id == "EVT-FIXED-002"


def test_sequences_are_aggregate_local():
    # Two different aggregates can both have sequence 1.
    request_a = OrderRequestFactory().create(
        valid_context(intent_id="INT-A"),
        order_type="MARKET",
        time_in_force="DAY",
        limit_price=None,
        created_at=1000,
    )
    request_b = OrderRequestFactory().create(
        valid_context(intent_id="INT-B"),
        order_type="MARKET",
        time_in_force="DAY",
        limit_price=None,
        created_at=1000,
    )
    factory = OrderRequestEventFactory()
    event_a = factory.create(
        request_a,
        OrderRequestEventType.ORDER_REQUEST_CREATED,
        sequence=1,
        causation_id=None,
        timestamp=1000,
    )
    event_b = factory.create(
        request_b,
        OrderRequestEventType.ORDER_REQUEST_CREATED,
        sequence=1,
        causation_id=None,
        timestamp=1000,
    )
    assert event_a.sequence == event_b.sequence == 1
    assert event_a.aggregate_id != event_b.aggregate_id
    assert event_a.event_id != event_b.event_id
