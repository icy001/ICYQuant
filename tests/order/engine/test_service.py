"""Tests for the order engine service (Commit 33 Part 1.2 / 1.3)."""

from __future__ import annotations

from datetime import datetime

import pytest

from services.order.domain.order_status import OrderStatus
from services.order.domain.order_state import InvalidOrderStateTransition
from services.order.engine.execution.response import (
    ExecutionResponse,
    ExecutionResponseStatus,
)
from services.order.engine.repository import OrderPersistenceError
from services.order.engine.service import (
    OrderEngineService,
    OrderNotFoundError,
)
from services.order.engine.validator import OrderValidationError
from services.order.request.state import OrderRequestState

TS = datetime(2026, 8, 13, 9, 30, 0)


# --- Spec #30: create ------------------------------------------------------


def test_service_creates_order(
    service: OrderEngineService, make_handoff_request, make_create_command
):
    request = make_handoff_request()
    command = make_create_command(request)

    order = service.create(request, command)

    assert order.status is OrderStatus.CREATED
    assert order.order_request_id == request.order_request_id


def test_create_persists_before_returning(
    service: OrderEngineService,
    repository,
    make_handoff_request,
    make_create_command,
):
    request = make_handoff_request()
    order = service.create(request, make_create_command(request))

    stored = repository.get(order.order_id)
    assert stored is not None
    assert stored.order_id == order.order_id


def test_create_rejects_non_handoff_request(
    service: OrderEngineService, make_request, make_create_command
):
    request = make_request(state=OrderRequestState.NORMALIZED)

    with pytest.raises(OrderValidationError):
        service.create(request, make_create_command(request))


def test_create_persist_failure_fails_closed(
    service: OrderEngineService,
    repository,
    make_handoff_request,
    make_create_command,
):
    # Spec #18: validate -> create -> persist -> return.  A persist failure
    # means the order was never created.
    repository.fail_on_save = True
    with pytest.raises(OrderPersistenceError):
        service.create(make_handoff_request(), make_create_command(make_handoff_request()))
    assert not repository._orders


# --- Spec #31: submit -------------------------------------------------------


def test_service_submits_order(
    service: OrderEngineService,
    repository,
    make_order,
    make_submit_command,
):
    order = make_order(status=OrderStatus.CREATED)
    repository.save(order)

    updated = service.submit(make_submit_command(order))

    # Part 1.3: submit drives CREATED -> PENDING_SUBMIT -> SUBMITTED, then the
    # paper gateway accepts the order and attaches the venue order id.
    assert updated.status is OrderStatus.ACCEPTED
    assert updated.venue_order_id is not None


def test_submit_is_idempotent(
    service: OrderEngineService,
    repository,
    make_order,
    make_submit_command,
):
    # Spec #26: an order already past submission is a no-op - the service never
    # sends it through the execution boundary a second time.
    order = make_order(status=OrderStatus.SUBMITTED)
    repository.save(order)

    updated = service.submit(make_submit_command(order))

    assert updated.status is OrderStatus.SUBMITTED
    assert updated is order


# --- Spec #32: accept -------------------------------------------------------


def test_service_accepts_order(
    service: OrderEngineService,
    repository,
    make_order,
    make_accept_command,
):
    order = make_order(status=OrderStatus.SUBMITTED)
    repository.save(order)

    updated = service.accept(make_accept_command(order))

    assert updated.status is OrderStatus.ACCEPTED


def test_accept_is_idempotent(
    service: OrderEngineService,
    repository,
    make_order,
    make_accept_command,
):
    # Spec #27: a repeated accept is a no-op.
    order = make_order(status=OrderStatus.ACCEPTED)
    repository.save(order)

    updated = service.accept(make_accept_command(order))

    assert updated.status is OrderStatus.ACCEPTED
    assert updated is order


# --- Spec #33: reject --------------------------------------------------------


def test_service_rejects_order(
    service: OrderEngineService,
    repository,
    make_order,
    make_reject_command,
):
    order = make_order(status=OrderStatus.SUBMITTED)
    repository.save(order)

    updated = service.reject(
        make_reject_command(order, reason="BROKER_REJECTED")
    )

    assert updated.status is OrderStatus.REJECTED
    assert updated.reject_reason == "BROKER_REJECTED"


# --- Spec #34: cancel --------------------------------------------------------


def test_service_starts_cancel(
    service: OrderEngineService,
    repository,
    make_order,
    make_cancel_command,
):
    order = make_order(status=OrderStatus.ACCEPTED)
    repository.save(order)

    updated = service.cancel(make_cancel_command(order))

    assert updated.status is OrderStatus.CANCEL_PENDING


# --- Spec #35: invalid transition -------------------------------------------


def test_service_rejects_invalid_transition(
    service: OrderEngineService,
    repository,
    make_order,
    make_cancel_command,
):
    # Spec #28: FILLED is terminal; a cancel request must be rejected.
    order = make_order(status=OrderStatus.FILLED)
    repository.save(order)

    with pytest.raises(InvalidOrderStateTransition):
        service.cancel(make_cancel_command(order))


# --- Spec #36: lineage preservation ------------------------------------------


def test_service_preserves_lineage(
    service: OrderEngineService, make_handoff_request, make_create_command
):
    request = make_handoff_request(
        intent_id="INT-001",
        authorization_id="AUTH-001",
        certificate_id="CERT-001",
        decision_id="DEC-001",
    )

    order = service.create(request, make_create_command(request))

    assert order.intent_id == "INT-001"
    assert order.authorization_id == "AUTH-001"
    assert order.certificate_id == "CERT-001"
    assert order.decision_id == "DEC-001"


# --- Additional service behaviour --------------------------------------------


def test_service_expires_order(
    service: OrderEngineService,
    repository,
    make_order,
    make_expire_command,
):
    order = make_order(status=OrderStatus.ACCEPTED)
    repository.save(order)

    updated = service.expire(make_expire_command(order))

    assert updated.status is OrderStatus.EXPIRED


def test_transition_is_persisted(
    service: OrderEngineService,
    repository,
    make_order,
    make_accept_command,
):
    # Spec #19: persist before returning; repository and memory agree.
    order = make_order(status=OrderStatus.SUBMITTED)
    repository.save(order)

    updated = service.accept(make_accept_command(order))

    stored = repository.get(order.order_id)
    assert stored is updated
    assert stored.status is OrderStatus.ACCEPTED


def test_update_failure_fails_closed(
    service: OrderEngineService,
    repository,
    make_order,
    make_accept_command,
):
    order = make_order(status=OrderStatus.SUBMITTED)
    repository.save(order)
    repository.fail_on_update = True

    with pytest.raises(OrderPersistenceError):
        service.accept(make_accept_command(order))
    # Memory state was never advanced past SUBMITTED.
    assert repository.get(order.order_id).status is OrderStatus.SUBMITTED


def test_service_rejects_unknown_order(
    service: OrderEngineService, make_order, make_submit_command
):
    order = make_order()  # never persisted

    with pytest.raises(OrderNotFoundError):
        service.submit(make_submit_command(order))


def test_service_full_flow(
    service: OrderEngineService,
    repository,
    gateway,
    make_handoff_request,
    make_create_command,
    make_submit_command,
    make_accept_command,
):
    request = make_handoff_request()
    order = service.create(request, make_create_command(request))

    # The gateway answers PENDING, so submit stops at SUBMITTED (query-before-
    # retry, Part 1.3); the explicit accept command then completes the flow.
    gateway.default_response = ExecutionResponse(
        execution_request_id="EXREQ-FLOW-000001",
        order_id=order.order_id,
        status=ExecutionResponseStatus.PENDING,
        venue_order_id=None,
        reject_reason=None,
        timestamp=TS,
        correlation_id="CORR-001",
    )

    submitted = service.submit(make_submit_command(order))
    assert submitted.status is OrderStatus.SUBMITTED

    accepted = service.accept(make_accept_command(submitted))
    assert accepted.status is OrderStatus.ACCEPTED

    final = repository.get(order.order_id)
    assert final.status is OrderStatus.ACCEPTED
    assert final.order_request_id == request.order_request_id
