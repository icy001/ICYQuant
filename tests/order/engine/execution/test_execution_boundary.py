"""End-to-end execution boundary tests (Commit 33 Part 1.3 #14-#26).

These tests drive :class:`OrderEngineService.submit` through the adapter and
the paper gateway and pin the response mapping:

* ACCEPTED -> Order ACCEPTED (+ venue_order_id)
* REJECTED -> Order REJECTED (+ reject_reason)
* PENDING / UNKNOWN -> Order stays SUBMITTED (query before retry)
* gateway failure -> fail-closed: order stays durably SUBMITTED, never a fake
  ACCEPTED / FILLED
"""

from __future__ import annotations

from datetime import datetime

import pytest

from services.order.domain.order_status import OrderStatus
from services.order.engine.execution.errors import (
    ExecutionTimeoutError,
    ExecutionUnavailableError,
)
from services.order.engine.execution.response import (
    ExecutionResponse,
    ExecutionResponseStatus,
)

TS = datetime(2026, 8, 13, 9, 30, 0)


def _canned(
    status: ExecutionResponseStatus,
    order_id: str,
    *,
    venue: str | None = None,
    reason: str | None = None,
) -> ExecutionResponse:
    return ExecutionResponse(
        execution_request_id="EXREQ-CANNED",
        order_id=order_id,
        status=status,
        venue_order_id=venue,
        reject_reason=reason,
        timestamp=TS,
        correlation_id="CORR-001",
    )


def test_submit_accepted_maps_to_accepted_order(
    service, repository, make_order, make_submit_command
):
    order = make_order(status=OrderStatus.CREATED)
    repository.save(order)

    updated = service.submit(make_submit_command(order))

    assert updated.status is OrderStatus.ACCEPTED
    assert updated.venue_order_id == "VENUE-000001"
    assert repository.get(order.order_id) is updated


def test_submit_rejected_maps_to_rejected_order(
    service, gateway, repository, make_order, make_submit_command
):
    order = make_order(status=OrderStatus.CREATED)
    repository.save(order)
    gateway.default_response = _canned(
        ExecutionResponseStatus.REJECTED, order.order_id, reason="EXECUTION_REJECTED"
    )

    updated = service.submit(make_submit_command(order))

    assert updated.status is OrderStatus.REJECTED
    assert updated.reject_reason == "EXECUTION_REJECTED"


def test_submit_unknown_keeps_order_submitted(
    service, gateway, repository, make_order, make_submit_command
):
    # Spec #7: UNKNOWN != REJECTED - the order stays SUBMITTED and must be
    # queried / reconciled before any retry.
    order = make_order(status=OrderStatus.CREATED)
    repository.save(order)
    gateway.default_response = _canned(ExecutionResponseStatus.UNKNOWN, order.order_id)

    updated = service.submit(make_submit_command(order))

    assert updated.status is OrderStatus.SUBMITTED
    assert updated.venue_order_id is None
    assert gateway.query(order.order_id) is not None  # query-before-retry


def test_submit_pending_keeps_order_submitted(
    service, gateway, repository, make_order, make_submit_command
):
    order = make_order(status=OrderStatus.CREATED)
    repository.save(order)
    gateway.default_response = _canned(ExecutionResponseStatus.PENDING, order.order_id)

    updated = service.submit(make_submit_command(order))

    assert updated.status is OrderStatus.SUBMITTED


def test_submit_is_idempotent_after_submission(
    service, repository, make_order, make_submit_command
):
    # An order already past the submission flow is a no-op.
    order = make_order(status=OrderStatus.SUBMITTED)
    repository.save(order)

    updated = service.submit(make_submit_command(order))

    assert updated is order
    assert updated.status is OrderStatus.SUBMITTED


def test_gateway_unavailable_fails_closed(
    service, gateway, repository, make_order, make_submit_command
):
    # Spec #26: never fake an ACCEPTED - the engine stops and the order stays
    # durably SUBMITTED.
    order = make_order(status=OrderStatus.CREATED)
    repository.save(order)
    gateway.fail_on_submit = True

    with pytest.raises(ExecutionUnavailableError):
        service.submit(make_submit_command(order))

    stored = repository.get(order.order_id)
    assert stored.status is OrderStatus.SUBMITTED
    assert stored.venue_order_id is None


def test_timeout_requires_query_before_retry(
    service, gateway, repository, make_order, make_submit_command
):
    # Spec #22: a timeout is not a rejection - the engine stops, the order is
    # durable at SUBMITTED, and the caller must query before it ever retries.
    order = make_order(status=OrderStatus.CREATED)
    repository.save(order)
    gateway.timeout_on_submit = True

    with pytest.raises(ExecutionTimeoutError):
        service.submit(make_submit_command(order))

    stored = repository.get(order.order_id)
    assert stored.status is OrderStatus.SUBMITTED
    assert gateway.query(order.order_id) is None  # nothing known yet


def test_submit_uses_a_fresh_execution_request_id(
    service, gateway, repository, make_order, make_submit_command
):
    # Every submission attempt carries its own EXREQ id (#18).
    order = make_order(status=OrderStatus.CREATED)
    repository.save(order)

    service.submit(make_submit_command(order))

    response = gateway.query(order.order_id)
    assert response is not None
    assert response.execution_request_id.startswith("EXREQ-")


def test_duplicate_submit_never_resends_to_venue(
    service, gateway, repository, make_order, make_submit_command
):
    order = make_order(status=OrderStatus.CREATED)
    repository.save(order)

    first = service.submit(make_submit_command(order))
    second = service.submit(make_submit_command(order))

    assert second is first  # service-level idempotency
    response = gateway.query(order.order_id)
    assert gateway.submission_count(response.execution_request_id) == 1


def test_submit_preserves_lineage(
    service, repository, make_order, make_submit_command
):
    # The authorization lineage is fixed at creation and can never be
    # overwritten by the execution layer (Part 1.1 #22).
    order = make_order(
        status=OrderStatus.CREATED,
        intent_id="INT-007",
        authorization_id="AUTH-007",
        certificate_id="CERT-007",
        decision_id="DEC-007",
    )
    repository.save(order)

    updated = service.submit(make_submit_command(order))

    assert updated.status is OrderStatus.ACCEPTED
    assert updated.intent_id == "INT-007"
    assert updated.authorization_id == "AUTH-007"
    assert updated.certificate_id == "CERT-007"
    assert updated.decision_id == "DEC-007"
    assert updated.strategy_id == order.strategy_id
