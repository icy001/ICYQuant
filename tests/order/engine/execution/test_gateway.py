"""Tests for the fake execution gateway (Commit 33 Part 1.3 #21/#22/#26).

The paper gateway can simulate ACCEPTED / REJECTED / PENDING / UNKNOWN /
TIMEOUT / UNAVAILABLE.  Submitting the same execution request twice replays the
stored response and never re-sends the order to the venue.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest

from services.order.domain.order_side import OrderSide
from services.order.domain.order_type import OrderType
from services.order.domain.time_in_force import TimeInForce
from services.order.engine.execution.errors import (
    ExecutionTimeoutError,
    ExecutionUnavailableError,
)
from services.order.engine.execution.request import ExecutionRequest
from services.order.engine.execution.response import (
    ExecutionResponse,
    ExecutionResponseStatus,
)

TS = datetime(2026, 8, 13, 9, 30, 0)


def _make_request(
    execution_request_id: str = "EXREQ-20260813-000001",
    order_id: str = "ORD-1",
    **overrides,
) -> ExecutionRequest:
    defaults = dict(
        execution_request_id=execution_request_id,
        order_id=order_id,
        client_order_id="ICY-ORD-1",
        symbol="NVDA",
        side=OrderSide.BUY,
        quantity=Decimal("100"),
        order_type=OrderType.MARKET,
        time_in_force=TimeInForce.DAY,
        limit_price=None,
        correlation_id="CORR-001",
        causation_id=None,
        timestamp=TS,
    )
    defaults.update(overrides)
    return ExecutionRequest(**defaults)


def test_default_submit_accepts_with_venue_id(gateway):
    response = gateway.submit(_make_request())

    assert response.status is ExecutionResponseStatus.ACCEPTED
    assert response.venue_order_id == "VENUE-000001"
    assert response.order_id == "ORD-1"
    assert response.correlation_id == "CORR-001"


def test_venue_ids_are_monotonic(gateway):
    first = gateway.submit(
        _make_request(execution_request_id="EXREQ-1", order_id="ORD-1")
    )
    second = gateway.submit(
        _make_request(execution_request_id="EXREQ-2", order_id="ORD-2")
    )
    assert first.venue_order_id == "VENUE-000001"
    assert second.venue_order_id == "VENUE-000002"
    assert first.venue_order_id != second.venue_order_id


def test_submit_replays_for_the_same_execution_request(gateway):
    request = _make_request(execution_request_id="EXREQ-20260813-000001")
    first = gateway.submit(request)
    second = gateway.submit(request)

    assert first is second  # idempotent replay, no re-send
    assert gateway.submission_count(request.execution_request_id) == 1


def test_submission_count_tracks_real_sends(gateway):
    assert gateway.submission_count("EXREQ-X") == 0
    gateway.submit(_make_request(execution_request_id="EXREQ-X"))
    assert gateway.submission_count("EXREQ-X") == 1
    gateway.submit(_make_request(execution_request_id="EXREQ-X"))
    assert gateway.submission_count("EXREQ-X") == 1


def test_default_response_is_returned_as_is(gateway):
    canned = ExecutionResponse(
        execution_request_id="EXREQ-9",
        order_id="ORD-9",
        status=ExecutionResponseStatus.PENDING,
        venue_order_id=None,
        reject_reason=None,
        timestamp=TS,
        correlation_id="CORR-001",
    )
    gateway.default_response = canned

    response = gateway.submit(
        _make_request(execution_request_id="EXREQ-9", order_id="ORD-9")
    )

    assert response is canned


def test_fail_on_submit_raises_unavailable(gateway):
    gateway.fail_on_submit = True
    with pytest.raises(ExecutionUnavailableError):
        gateway.submit(_make_request())


def test_timeout_on_submit_raises_timeout_and_sends_nothing(gateway):
    gateway.timeout_on_submit = True
    with pytest.raises(ExecutionTimeoutError):
        gateway.submit(
            _make_request(execution_request_id="EXREQ-TIMEOUT", order_id="ORD-T")
        )
    # Nothing was sent and nothing is known: query before retry (spec #22).
    assert gateway.query("ORD-T") is None
    assert gateway.submission_count("EXREQ-TIMEOUT") == 0


def test_cancel_is_replayed(gateway):
    request = _make_request(execution_request_id="EXREQ-C1", order_id="ORD-C")
    first = gateway.cancel(request)
    second = gateway.cancel(request)

    assert first is second
    assert gateway.query("ORD-C") is first


def test_fail_on_cancel_raises_unavailable(gateway):
    gateway.fail_on_cancel = True
    with pytest.raises(ExecutionUnavailableError):
        gateway.cancel(_make_request())


def test_timeout_on_cancel_raises_timeout(gateway):
    gateway.timeout_on_cancel = True
    with pytest.raises(ExecutionTimeoutError):
        gateway.cancel(_make_request())


def test_query_returns_none_for_unknown_order(gateway):
    assert gateway.query("ORD-NOPE") is None


def test_query_returns_latest_known_response(gateway):
    request = _make_request(execution_request_id="EXREQ-Q1", order_id="ORD-Q")
    response = gateway.submit(request)
    assert gateway.query("ORD-Q") is response
