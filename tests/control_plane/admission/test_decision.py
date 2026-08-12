"""Tests for AdmissionDecision / OrderAdmissionDecision (spec section 4)."""
from __future__ import annotations

from dataclasses import FrozenInstanceError
from uuid import uuid4

import pytest

from services.control_plane.admission.decision import (
    AdmissionDecision,
    AdmissionReason,
    OrderAdmissionDecision,
)


def test_decision_values():
    assert AdmissionDecision.ACCEPTED.value == "ACCEPTED"
    assert AdmissionDecision.ACCEPTED_REDUCE_ONLY.value == "ACCEPTED_REDUCE_ONLY"
    assert AdmissionDecision.REJECTED.value == "REJECTED"


def test_accepted_property():
    assert AdmissionDecision.ACCEPTED.accepted is True
    assert AdmissionDecision.ACCEPTED_REDUCE_ONLY.accepted is True
    assert AdmissionDecision.REJECTED.accepted is False


def test_reason_values():
    assert AdmissionReason.CONTROL_ALLOWED.value == "CONTROL_ALLOWED"
    assert AdmissionReason.CONTROL_REDUCE_ONLY.value == "CONTROL_REDUCE_ONLY"
    assert AdmissionReason.CONTROL_BLOCKED.value == "CONTROL_BLOCKED"
    assert AdmissionReason.RISK_REJECTED.value == "RISK_REJECTED"
    assert AdmissionReason.INVALID_REQUEST.value == "INVALID_REQUEST"


def test_decision_carries_request_id_and_message():
    request_id = uuid4()
    decision = OrderAdmissionDecision(
        decision=AdmissionDecision.REJECTED,
        reason=AdmissionReason.INVALID_REQUEST,
        request_id=request_id,
        message="symbol is required",
    )

    assert decision.decision is AdmissionDecision.REJECTED
    assert decision.reason is AdmissionReason.INVALID_REQUEST
    assert decision.request_id == request_id
    assert decision.message == "symbol is required"
    assert decision.control_result is None
    assert decision.risk_result is None


def test_decision_is_frozen():
    decision = OrderAdmissionDecision(
        decision=AdmissionDecision.ACCEPTED,
        reason=AdmissionReason.CONTROL_ALLOWED,
        request_id=uuid4(),
    )

    with pytest.raises(FrozenInstanceError):
        decision.message = "changed"  # type: ignore[misc]
