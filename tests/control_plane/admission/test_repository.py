"""Tests for AdmissionRepository idempotency (spec section 15)."""
from __future__ import annotations

from uuid import uuid4

from services.control_plane.admission.decision import (
    AdmissionDecision,
    AdmissionReason,
    OrderAdmissionDecision,
)
from services.control_plane.admission.repository import (
    AdmissionRepository,
)


def _decision(request_id=None):
    return OrderAdmissionDecision(
        decision=AdmissionDecision.ACCEPTED,
        reason=AdmissionReason.CONTROL_ALLOWED,
        request_id=request_id or uuid4(),
    )


def test_get_returns_none_for_unknown():
    repository = AdmissionRepository()

    assert repository.get(uuid4()) is None
    assert repository.has(uuid4()) is False


def test_save_and_get_round_trip():
    repository = AdmissionRepository()
    decision = _decision()

    repository.save(decision)

    assert repository.get(decision.request_id) is decision
    assert repository.has(decision.request_id) is True


def test_save_overwrites_same_request_id():
    repository = AdmissionRepository()
    request_id = uuid4()

    first = _decision(request_id)
    second = OrderAdmissionDecision(
        decision=AdmissionDecision.REJECTED,
        reason=AdmissionReason.CONTROL_BLOCKED,
        request_id=request_id,
        message="overwritten",
    )

    repository.save(first)
    repository.save(second)

    # Latest save wins for the same request_id.
    assert repository.get(request_id) is second


def test_count_and_clear():
    repository = AdmissionRepository()
    repository.save(_decision())
    repository.save(_decision())

    assert repository.count() == 2

    repository.clear()

    assert repository.count() == 0
