"""Tests for the OrderRequestService boundary (Commit 32 Part 1.5).

The service is the only application boundary: it composes Factory, Validator,
Normalizer, Lifecycle and Repository, enforces idempotency, and fails closed
when the repository is unavailable.
"""

import pytest

from services.order.request.errors import OrderRequestValidationError
from services.order.request.event_types import OrderRequestEventType
from services.order.request.exceptions import OrderRequestPersistenceError
from services.order.request.lifecycle import InvalidStateTransition
from services.order.request.repository import (
    InMemoryOrderRequestRepository,
    OrderRequestSnapshot,
)
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
def repository() -> InMemoryOrderRequestRepository:
    return InMemoryOrderRequestRepository()


@pytest.fixture
def service(repository) -> OrderRequestService:
    return OrderRequestService(repository=repository)


def create_market_request(service, *, created_at=1000.0):
    return service.create(
        valid_context(),
        order_type="MARKET",
        time_in_force="DAY",
        limit_price=None,
        created_at=created_at,
    )


# --- spec tests (#20-#26) ------------------------------------------------------


def test_create_order_request(service):
    request = service.create(
        valid_context(),
        order_type="MARKET",
        time_in_force="DAY",
        limit_price=None,
        created_at=1000,
    )
    assert request.state == OrderRequestState.CREATED


def test_full_service_flow(service, repository):
    request = service.create(
        valid_context(),
        order_type="MARKET",
        time_in_force="DAY",
        limit_price=None,
        created_at=1000,
    )

    service.validate(request)

    normalized = service.normalize(request)

    service.submit(
        normalized.order_request_id,
        timestamp=1001,
    )

    service.accept(
        normalized.order_request_id,
        timestamp=1002,
    )

    service.handoff(
        normalized.order_request_id,
        timestamp=1003,
    )

    final = repository.get(
        normalized.order_request_id
    )

    assert final.state == OrderRequestState.HANDOFF


def test_create_is_idempotent(service):
    first = service.create(
        valid_context(),
        order_type="MARKET",
        time_in_force="DAY",
        limit_price=None,
        created_at=1000,
    )

    second = service.create(
        valid_context(),
        order_type="MARKET",
        time_in_force="DAY",
        limit_price=None,
        created_at=1001,
    )

    assert first.order_request_id == second.order_request_id
    # Idempotent create must not emit a second ORDER_REQUEST_CREATED event.
    assert len(service.get_events(first.order_request_id)) == 1


def test_submit_is_idempotent(service, repository):
    request = create_market_request(service)
    service.validate(request, timestamp=1001)
    service.normalize(request, timestamp=1002)

    service.submit(
        request.order_request_id,
        timestamp=1000,
    )

    service.submit(
        request.order_request_id,
        timestamp=1001,
    )

    stored = repository.get(
        request.order_request_id
    )

    assert stored.state == OrderRequestState.SUBMITTED
    assert service.get_state(request.order_request_id) == OrderRequestState.SUBMITTED


def test_repository_failure_fails_closed(service, repository):
    repository.fail_on_save = True

    with pytest.raises(
        OrderRequestPersistenceError
    ):
        service.create(
            valid_context(),
            order_type="MARKET",
            time_in_force="DAY",
            limit_price=None,
            created_at=1000,
        )


def test_service_rejects_invalid_transition(service):
    request = create_market_request(service)

    with pytest.raises(
        InvalidStateTransition
    ):
        service.accept(
            request.order_request_id,
            timestamp=1000,
        )


def test_lineage_survives_service_flow(service):
    request = service.create(
        valid_context(
            intent_id="INT-001",
            authorization_id="AUTH-001",
            certificate_id="CERT-001",
            decision_id="RISK-001",
        ),
        order_type="MARKET",
        time_in_force="DAY",
        limit_price=None,
        created_at=1000,
    )

    assert request.intent_id == "INT-001"
    assert request.authorization_id == "AUTH-001"
    assert request.certificate_id == "CERT-001"
    assert request.decision_id == "RISK-001"


# --- Part 1.5 reliability guarantees --------------------------------------------


def test_create_returns_snapshot_with_state(service):
    request = create_market_request(service)
    assert isinstance(request, OrderRequestSnapshot)
    assert request.state == OrderRequestState.CREATED


def test_validate_accepts_request_object(service):
    request = create_market_request(service)
    # The spec boundary accepts the request object, not only the id.
    service.validate(request)
    assert service.get_state(request.order_request_id) == OrderRequestState.VALIDATED


def test_repository_failure_prevents_state_change(service, repository):
    request = create_market_request(service)
    service.validate(request, timestamp=1001)
    service.normalize(request, timestamp=1002)

    repository.fail_on_update = True

    with pytest.raises(OrderRequestPersistenceError):
        service.submit(request.order_request_id, timestamp=1003)

    # Persist-then-transition: neither memory nor repository moved, and no
    # SUBMITTED event was emitted (the log stops at NORMALIZED).
    assert service.get_state(request.order_request_id) == OrderRequestState.NORMALIZED
    assert repository.get(request.order_request_id).state == OrderRequestState.NORMALIZED
    events = service.get_events(request.order_request_id)
    assert [e.event_type for e in events] == [
        OrderRequestEventType.ORDER_REQUEST_CREATED,
        OrderRequestEventType.ORDER_REQUEST_VALIDATED,
        OrderRequestEventType.ORDER_REQUEST_NORMALIZED,
    ]


def test_transition_returns_snapshot_with_new_state(service):
    request = create_market_request(service)
    service.validate(request, timestamp=1001)
    service.normalize(request, timestamp=1002)
    submitted = service.submit(request.order_request_id, timestamp=1003)
    assert submitted.state == OrderRequestState.SUBMITTED
    assert submitted.order_request_id == request.order_request_id


def test_repository_is_source_of_truth(service, repository):
    request = create_market_request(service)
    service.validate(request, timestamp=1001)

    # A fresh service instance recovers the aggregate from the repository.
    fresh = OrderRequestService(repository=repository)
    assert fresh.get_state(request.order_request_id) == OrderRequestState.VALIDATED
    assert fresh.get(request.order_request_id).state == OrderRequestState.VALIDATED


def test_reject_persists_rejected_state(service, repository):
    request = create_market_request(service)
    service.validate(request, timestamp=1001)
    service.normalize(request, timestamp=1002)
    service.submit(request.order_request_id, timestamp=1003)
    service.reject(request.order_request_id, timestamp=1004, reason="VENUE_UNAVAILABLE")

    assert service.get_state(request.order_request_id) == OrderRequestState.REJECTED
    assert repository.get(request.order_request_id).state == OrderRequestState.REJECTED


def test_validation_failure_never_reaches_repository(service, repository):
    request = service.create(
        valid_context(symbol="NV DA"),  # invalid symbol: cannot be auto-repaired
        order_type="MARKET",
        time_in_force="DAY",
        limit_price=None,
        created_at=1000,
    )
    with pytest.raises(OrderRequestValidationError):
        service.validate(request, timestamp=1001)
    assert service.get_state(request.order_request_id) == OrderRequestState.CREATED
    assert repository.get(request.order_request_id).state == OrderRequestState.CREATED
