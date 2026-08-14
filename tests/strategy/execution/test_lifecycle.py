"""Tests for the execution intent lifecycle state machine."""

import pytest

from services.strategy.execution.intent import ExecutionIntentState
from services.strategy.execution.lifecycle import (
    IntentLifecycle,
    IntentLifecycleError,
)


def make_lifecycle(state: str = "PENDING") -> IntentLifecycle:
    return IntentLifecycle("INTENT-20260813-000001", state=state)


def test_intent_id_required() -> None:
    with pytest.raises(ValueError):
        IntentLifecycle("")


def test_default_state_is_pending() -> None:
    assert make_lifecycle().state == ExecutionIntentState.PENDING.value


def test_pending_to_validated_to_submitted() -> None:
    lifecycle = make_lifecycle()
    assert lifecycle.transition("VALIDATED") == "VALIDATED"
    assert lifecycle.transition("SUBMITTED") == "SUBMITTED"
    assert lifecycle.state == "SUBMITTED"


def test_illegal_pending_to_submitted_raises() -> None:
    lifecycle = make_lifecycle()
    with pytest.raises(IntentLifecycleError):
        lifecycle.transition("SUBMITTED")
    # a failed transition leaves the state unchanged
    assert lifecycle.state == "PENDING"


def test_illegal_transition_is_value_error() -> None:
    # IntentLifecycleError subclasses ValueError so callers can catch either.
    with pytest.raises(ValueError):
        make_lifecycle().transition("SUBMITTED")


def test_terminal_state_accepts_no_transition() -> None:
    for terminal in ("REJECTED", "EXPIRED", "CANCELLED"):
        lifecycle = make_lifecycle(state=terminal)
        with pytest.raises(IntentLifecycleError):
            lifecycle.transition("SUBMITTED")
        assert lifecycle.state == terminal


def test_allowed_transitions_table() -> None:
    assert IntentLifecycle.ALLOWED_TRANSITIONS["PENDING"] == frozenset(
        {"VALIDATED", "REJECTED", "EXPIRED", "CANCELLED"}
    )
    assert IntentLifecycle.ALLOWED_TRANSITIONS["VALIDATED"] == frozenset(
        {"SUBMITTED", "REJECTED", "EXPIRED", "CANCELLED"}
    )
    assert IntentLifecycle.ALLOWED_TRANSITIONS["SUBMITTED"] == frozenset(
        {"REJECTED", "EXPIRED", "CANCELLED"}
    )
    assert IntentLifecycle.ALLOWED_TRANSITIONS["REJECTED"] == frozenset()
    assert IntentLifecycle.ALLOWED_TRANSITIONS["EXPIRED"] == frozenset()
    assert IntentLifecycle.ALLOWED_TRANSITIONS["CANCELLED"] == frozenset()


def test_can_transition() -> None:
    lifecycle = make_lifecycle()
    assert lifecycle.can_transition("VALIDATED") is True
    assert lifecycle.can_transition("SUBMITTED") is False
    assert lifecycle.can_transition("CANCELLED") is True


def test_enum_state_inputs() -> None:
    lifecycle = IntentLifecycle(
        "INTENT-20260813-000001",
        state=ExecutionIntentState.PENDING,
    )
    assert lifecycle.state == "PENDING"
    assert lifecycle.transition(ExecutionIntentState.VALIDATED) == "VALIDATED"
    assert lifecycle.state == ExecutionIntentState.VALIDATED.value


def test_convenience_methods() -> None:
    lifecycle = make_lifecycle()
    assert lifecycle.validate() == "VALIDATED"
    assert lifecycle.submit() == "SUBMITTED"
    assert lifecycle.state == "SUBMITTED"


def test_cancel_from_pending() -> None:
    lifecycle = make_lifecycle()
    assert lifecycle.cancel() == "CANCELLED"
    assert lifecycle.state == "CANCELLED"


def test_reject_from_validated() -> None:
    lifecycle = make_lifecycle()
    lifecycle.validate()
    assert lifecycle.reject() == "REJECTED"


def test_expire_from_submitted() -> None:
    lifecycle = make_lifecycle()
    lifecycle.validate()
    lifecycle.submit()
    assert lifecycle.expire() == "EXPIRED"
