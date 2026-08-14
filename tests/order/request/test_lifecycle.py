"""Tests for the order request state machine (Commit 32 Part 1.3)."""

from dataclasses import FrozenInstanceError

import pytest

from services.order.request.lifecycle import (
    InvalidStateTransition,
    OrderRequestLifecycle,
    OrderRequestStateTransition,
)
from services.order.request.state import OrderRequestState


@pytest.fixture
def lifecycle() -> OrderRequestLifecycle:
    return OrderRequestLifecycle()


def test_created_to_validated(lifecycle):
    result = lifecycle.transition(
        request_id="OR-001",
        current_state=OrderRequestState.CREATED,
        target_state=OrderRequestState.VALIDATED,
        correlation_id="CORR-001",
        timestamp=1000,
    )
    assert result.to_state == OrderRequestState.VALIDATED


def test_created_cannot_jump_to_accepted(lifecycle):
    with pytest.raises(InvalidStateTransition):
        lifecycle.transition(
            request_id="OR-001",
            current_state=OrderRequestState.CREATED,
            target_state=OrderRequestState.ACCEPTED,
            correlation_id="CORR-001",
            timestamp=1000,
        )


def test_rejected_is_terminal(lifecycle):
    with pytest.raises(InvalidStateTransition):
        lifecycle.transition(
            request_id="OR-001",
            current_state=OrderRequestState.REJECTED,
            target_state=OrderRequestState.ACCEPTED,
            correlation_id="CORR-001",
            timestamp=1000,
        )


def test_cancelled_is_terminal(lifecycle):
    with pytest.raises(InvalidStateTransition):
        lifecycle.transition(
            request_id="OR-001",
            current_state=OrderRequestState.CANCELLED,
            target_state=OrderRequestState.CREATED,
            correlation_id="CORR-001",
            timestamp=1000,
        )


def test_expired_is_terminal(lifecycle):
    with pytest.raises(InvalidStateTransition):
        lifecycle.transition(
            request_id="OR-001",
            current_state=OrderRequestState.EXPIRED,
            target_state=OrderRequestState.SUBMITTED,
            correlation_id="CORR-001",
            timestamp=1000,
        )


def test_handoff_is_terminal(lifecycle):
    with pytest.raises(InvalidStateTransition):
        lifecycle.transition(
            request_id="OR-001",
            current_state=OrderRequestState.HANDOFF,
            target_state=OrderRequestState.CREATED,
            correlation_id="CORR-001",
            timestamp=1000,
        )


def test_handoff_cannot_be_cancelled(lifecycle):
    with pytest.raises(InvalidStateTransition):
        lifecycle.transition(
            request_id="OR-001",
            current_state=OrderRequestState.HANDOFF,
            target_state=OrderRequestState.CANCELLED,
            correlation_id="CORR-001",
            timestamp=1000,
        )


def test_same_transition_is_idempotent(lifecycle):
    first = lifecycle.transition(
        request_id="OR-001",
        current_state=OrderRequestState.NORMALIZED,
        target_state=OrderRequestState.SUBMITTED,
        correlation_id="CORR-001",
        timestamp=1000,
    )
    second = lifecycle.transition(
        request_id="OR-001",
        current_state=OrderRequestState.SUBMITTED,
        target_state=OrderRequestState.SUBMITTED,
        correlation_id="CORR-001",
        timestamp=1001,
    )
    assert second.to_state == OrderRequestState.SUBMITTED
    assert second.from_state == OrderRequestState.SUBMITTED
    assert first.to_state == OrderRequestState.SUBMITTED


def test_terminal_same_state_is_rejected(lifecycle):
    with pytest.raises(InvalidStateTransition):
        lifecycle.transition(
            request_id="OR-001",
            current_state=OrderRequestState.REJECTED,
            target_state=OrderRequestState.REJECTED,
            correlation_id="CORR-001",
            timestamp=1000,
        )


def test_full_order_request_lifecycle(lifecycle):
    states = [
        OrderRequestState.CREATED,
        OrderRequestState.VALIDATED,
        OrderRequestState.NORMALIZED,
        OrderRequestState.SUBMITTED,
        OrderRequestState.ACCEPTED,
        OrderRequestState.HANDOFF,
    ]
    assert lifecycle.is_valid_path(states)


def test_reject_path(lifecycle):
    states = [
        OrderRequestState.SUBMITTED,
        OrderRequestState.REJECTED,
    ]
    assert lifecycle.is_valid_path(states)


def test_cancel_path(lifecycle):
    states = [
        OrderRequestState.CREATED,
        OrderRequestState.CANCELLED,
    ]
    assert lifecycle.is_valid_path(states)


def test_expiration_path(lifecycle):
    states = [
        OrderRequestState.NORMALIZED,
        OrderRequestState.EXPIRED,
    ]
    assert lifecycle.is_valid_path(states)


def test_invalid_path_is_detected(lifecycle):
    states = [
        OrderRequestState.CREATED,
        OrderRequestState.ACCEPTED,
    ]
    assert not lifecycle.is_valid_path(states)


def test_rejected_to_accepted_is_not_a_valid_path(lifecycle):
    states = [
        OrderRequestState.REJECTED,
        OrderRequestState.ACCEPTED,
    ]
    assert not lifecycle.is_valid_path(states)


def test_empty_path_is_valid(lifecycle):
    assert lifecycle.is_valid_path([])


def test_single_state_path_is_valid(lifecycle):
    assert lifecycle.is_valid_path([OrderRequestState.CREATED])


def test_duplicate_state_path_is_valid(lifecycle):
    states = [
        OrderRequestState.SUBMITTED,
        OrderRequestState.SUBMITTED,
        OrderRequestState.ACCEPTED,
    ]
    assert lifecycle.is_valid_path(states)


def test_transition_record_keeps_metadata(lifecycle):
    result = lifecycle.transition(
        request_id="OR-001",
        current_state=OrderRequestState.NORMALIZED,
        target_state=OrderRequestState.SUBMITTED,
        correlation_id="CORR-001",
        timestamp=1000,
        reason="ROUTING_DECISION",
    )
    assert result.request_id == "OR-001"
    assert result.from_state == OrderRequestState.NORMALIZED
    assert result.to_state == OrderRequestState.SUBMITTED
    assert result.reason == "ROUTING_DECISION"
    assert result.correlation_id == "CORR-001"
    assert result.timestamp == 1000


def test_reject_transition_preserves_reason(lifecycle):
    result = lifecycle.transition(
        request_id="OR-001",
        current_state=OrderRequestState.SUBMITTED,
        target_state=OrderRequestState.REJECTED,
        correlation_id="CORR-001",
        timestamp=1000,
        reason="VENUE_UNAVAILABLE",
    )
    assert result.to_state == OrderRequestState.REJECTED
    assert result.reason == "VENUE_UNAVAILABLE"


def test_transition_record_is_frozen(lifecycle):
    result = lifecycle.transition(
        request_id="OR-001",
        current_state=OrderRequestState.CREATED,
        target_state=OrderRequestState.VALIDATED,
        correlation_id="CORR-001",
        timestamp=1000,
    )
    with pytest.raises(FrozenInstanceError):
        result.to_state = OrderRequestState.REJECTED


def test_invalid_transition_is_a_value_error(lifecycle):
    with pytest.raises(ValueError):
        lifecycle.transition(
            request_id="OR-001",
            current_state=OrderRequestState.CREATED,
            target_state=OrderRequestState.HANDOFF,
            correlation_id="CORR-001",
            timestamp=1000,
        )


def test_can_transition_reflects_table(lifecycle):
    assert lifecycle.can_transition(
        OrderRequestState.CREATED, OrderRequestState.VALIDATED
    )
    assert not lifecycle.can_transition(
        OrderRequestState.CREATED, OrderRequestState.ACCEPTED
    )
    assert not lifecycle.can_transition(
        OrderRequestState.REJECTED, OrderRequestState.ACCEPTED
    )
    assert lifecycle.can_transition(
        OrderRequestState.ACCEPTED, OrderRequestState.HANDOFF
    )


def test_created_can_cancel(lifecycle):
    result = lifecycle.transition(
        request_id="OR-001",
        current_state=OrderRequestState.CREATED,
        target_state=OrderRequestState.CANCELLED,
        correlation_id="CORR-001",
        timestamp=1000,
    )
    assert result.to_state == OrderRequestState.CANCELLED


def test_normalized_can_expire(lifecycle):
    result = lifecycle.transition(
        request_id="OR-001",
        current_state=OrderRequestState.NORMALIZED,
        target_state=OrderRequestState.EXPIRED,
        correlation_id="CORR-001",
        timestamp=1000,
    )
    assert result.to_state == OrderRequestState.EXPIRED


def test_submitted_can_be_rejected(lifecycle):
    result = lifecycle.transition(
        request_id="OR-001",
        current_state=OrderRequestState.SUBMITTED,
        target_state=OrderRequestState.REJECTED,
        correlation_id="CORR-001",
        timestamp=1000,
    )
    assert result.to_state == OrderRequestState.REJECTED


def test_state_transition_type_is_exported():
    from services.order.request import OrderRequestStateTransition as exported

    assert exported is OrderRequestStateTransition


def test_state_and_lifecycle_are_exported():
    from services.order.request import (
        InvalidStateTransition as exported_error,
    )
    from services.order.request import (
        OrderRequestLifecycle as exported_lifecycle,
    )
    from services.order.request import OrderRequestState as exported_state

    assert exported_error is InvalidStateTransition
    assert exported_lifecycle is OrderRequestLifecycle
    assert exported_state is OrderRequestState
