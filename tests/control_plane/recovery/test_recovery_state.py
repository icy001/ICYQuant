"""Unit tests: recovery state machine + failure classification."""

from __future__ import annotations

import pytest

from services.control_plane.recovery.recovery_state import (
    FailureClass,
    RecoveryState,
    RecoveryStateMachine,
    RecoveryStateTransitionError,
    classify_failure,
)

HAPPY_PATH = [
    RecoveryState.DETECTED,
    RecoveryState.ISOLATING,
    RecoveryState.ISOLATED,
    RecoveryState.RECOVERING,
    RecoveryState.RECONCILING,
    RecoveryState.VERIFYING,
    RecoveryState.RAMPING_UP,
    RecoveryState.COMPLETED,
]


class TestRecoveryState:
    def test_lifecycle_values(self):
        assert [s.value for s in RecoveryState] == [
            "DETECTED",
            "ISOLATING",
            "ISOLATED",
            "RECOVERING",
            "RECONCILING",
            "VERIFYING",
            "RAMPING_UP",
            "COMPLETED",
            "FAILED",
            "ESCALATED",
        ]

    def test_terminal_states(self):
        assert RecoveryState.COMPLETED.is_terminal
        assert RecoveryState.ESCALATED.is_terminal
        assert not RecoveryState.RECOVERING.is_terminal

    def test_active_states(self):
        assert RecoveryState.RECOVERING.is_active
        assert RecoveryState.FAILED.is_active is False


class TestRecoveryStateMachine:
    def test_happy_path_transitions(self):
        for from_state, to_state in zip(HAPPY_PATH, HAPPY_PATH[1:]):
            assert RecoveryStateMachine.can_transition(from_state, to_state)
            RecoveryStateMachine.assert_transition(from_state, to_state)

    def test_cannot_skip_stages(self):
        assert not RecoveryStateMachine.can_transition(
            RecoveryState.DETECTED, RecoveryState.RECOVERING
        )
        assert not RecoveryStateMachine.can_transition(
            RecoveryState.ISOLATED, RecoveryState.VERIFYING
        )

    def test_any_stage_can_fail(self):
        for state in HAPPY_PATH[:-1]:  # COMPLETED is terminal
            assert RecoveryStateMachine.can_transition(state, RecoveryState.FAILED)
            assert RecoveryStateMachine.can_transition(state, RecoveryState.ESCALATED)

    def test_failed_can_retry_or_escalate(self):
        assert RecoveryStateMachine.can_transition(
            RecoveryState.FAILED, RecoveryState.RECOVERING
        )
        assert RecoveryStateMachine.can_transition(
            RecoveryState.FAILED, RecoveryState.ESCALATED
        )

    def test_terminal_states_have_no_outgoing(self):
        for state in (RecoveryState.COMPLETED, RecoveryState.ESCALATED):
            assert RecoveryStateMachine.ALLOWED_TRANSITIONS[state] == set()

    def test_assert_transition_raises(self):
        with pytest.raises(RecoveryStateTransitionError):
            RecoveryStateMachine.assert_transition(
                RecoveryState.DETECTED, RecoveryState.COMPLETED
            )


class TestFailureClassification:
    def test_timeout_is_transient(self):
        assert (
            classify_failure("connection to event store timed out")
            is FailureClass.TRANSIENT
        )

    def test_network_error_is_transient(self):
        assert (
            classify_failure("temporary network failure")
            is FailureClass.TRANSIENT
        )

    def test_event_gap_is_integrity(self):
        assert classify_failure("EVENT_GAP: missing event 102") is FailureClass.INTEGRITY

    def test_checksum_mismatch_is_integrity(self):
        assert (
            classify_failure("checksum mismatch detected") is FailureClass.INTEGRITY
        )

    def test_fatal_marker(self):
        assert classify_failure("fatal error in position service") is FailureClass.FATAL

    def test_unknown_defaults_to_recoverable(self):
        assert classify_failure("something odd happened") is FailureClass.RECOVERABLE

    def test_error_code_wins_over_text(self):
        assert (
            classify_failure("could not reach store", error_code="EVENT_GAP")
            is FailureClass.INTEGRITY
        )

    def test_transient_error_code(self):
        assert (
            classify_failure("boom", error_code="DB_TIMEOUT")
            is FailureClass.TRANSIENT
        )

    def test_empty_is_recoverable(self):
        assert classify_failure() is FailureClass.RECOVERABLE
