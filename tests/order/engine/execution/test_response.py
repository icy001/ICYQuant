"""Tests for the execution response model (Commit 33 Part 1.3 #7/#8).

``UNKNOWN`` is a first-class status: a network timeout does not mean the order
failed - the order keeps its state and must be queried / reconciled before any
retry (query-before-retry).
"""

from __future__ import annotations

import dataclasses
from datetime import datetime
from enum import Enum

import pytest

from services.order.engine.execution.response import (
    ExecutionResponse,
    ExecutionResponseStatus,
)

TS = datetime(2026, 8, 13, 9, 30, 0)


def test_status_members_are_first_class():
    assert issubclass(ExecutionResponseStatus, Enum)
    assert {status.value for status in ExecutionResponseStatus} == {
        "ACCEPTED",
        "REJECTED",
        "PENDING",
        "UNKNOWN",
    }


def test_unknown_is_not_rejected():
    # Spec #7: a timeout is not a rejection - UNKNOWN != REJECTED.
    assert ExecutionResponseStatus.UNKNOWN is not ExecutionResponseStatus.REJECTED
    assert ExecutionResponseStatus.UNKNOWN.value == "UNKNOWN"


def test_response_is_frozen():
    response = ExecutionResponse(
        execution_request_id="EXREQ-20260813-000001",
        order_id="ORD-20260813-000001",
        status=ExecutionResponseStatus.ACCEPTED,
        venue_order_id="VENUE-000001",
        reject_reason=None,
        timestamp=TS,
        correlation_id="CORR-001",
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        response.status = ExecutionResponseStatus.REJECTED


def test_rejected_response_carries_a_reason():
    response = ExecutionResponse(
        execution_request_id="EXREQ-1",
        order_id="ORD-1",
        status=ExecutionResponseStatus.REJECTED,
        venue_order_id=None,
        reject_reason="BROKER_REJECTED",
        timestamp=TS,
        correlation_id="CORR-001",
    )
    assert response.status is ExecutionResponseStatus.REJECTED
    assert response.reject_reason == "BROKER_REJECTED"
