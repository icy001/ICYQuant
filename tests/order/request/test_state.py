"""Tests for the OrderRequestState enum (Commit 32 Part 1.3)."""

from services.order.request.state import OrderRequestState


def test_states_have_stable_values():
    assert OrderRequestState.CREATED.value == "CREATED"
    assert OrderRequestState.VALIDATED.value == "VALIDATED"
    assert OrderRequestState.NORMALIZED.value == "NORMALIZED"
    assert OrderRequestState.SUBMITTED.value == "SUBMITTED"
    assert OrderRequestState.ACCEPTED.value == "ACCEPTED"
    assert OrderRequestState.REJECTED.value == "REJECTED"
    assert OrderRequestState.CANCELLED.value == "CANCELLED"
    assert OrderRequestState.EXPIRED.value == "EXPIRED"
    assert OrderRequestState.HANDOFF.value == "HANDOFF"


def test_state_is_a_str_enum():
    assert isinstance(OrderRequestState.CREATED, str)
    assert OrderRequestState.CREATED == "CREATED"


def test_all_lifecycle_states_are_defined():
    expected = {
        "CREATED",
        "VALIDATED",
        "NORMALIZED",
        "SUBMITTED",
        "ACCEPTED",
        "REJECTED",
        "CANCELLED",
        "EXPIRED",
        "HANDOFF",
    }
    assert {state.value for state in OrderRequestState} == expected


def test_state_is_comparable_to_its_value():
    assert OrderRequestState.SUBMITTED == "SUBMITTED"
