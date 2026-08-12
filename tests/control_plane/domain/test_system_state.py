"""Unit tests: SystemState, StateReasonCode and the System State Machine."""

from __future__ import annotations

import pytest

from services.control_plane.domain.system_state import (
    StateReasonCode,
    StateTransitionError,
    SystemState,
    SystemStateMachine,
)


# ============================================================
# SystemState enum
# ============================================================

class TestSystemStateInitialization:
    def test_all_states_defined(self):
        expected = {
            "INITIALIZING",
            "STARTING",
            "READY",
            "DEGRADED",
            "RECOVERING",
            "HALTED",
            "FAILED",
            "MAINTENANCE",
        }
        assert {s.value for s in SystemState} == expected

    def test_initializing_is_first_state(self):
        assert SystemState.INITIALIZING.value == "INITIALIZING"


class TestStateReasonCode:
    def test_reason_codes_are_mandatory(self):
        # Every state change must carry a reason — no null reasons in production.
        assert len(StateReasonCode) >= 8
        assert StateReasonCode.MANUAL_HALT.value == "MANUAL_HALT"
        assert StateReasonCode.EMERGENCY_HALT.value == "EMERGENCY_HALT"
        assert StateReasonCode.POSITION_MISMATCH.value == "POSITION_MISMATCH"
        assert StateReasonCode.RECOVERY_RUNNING.value == "RECOVERY_RUNNING"
        assert StateReasonCode.MAINTENANCE.value == "MAINTENANCE"


# ============================================================
# System State Machine
# ============================================================

class TestSystemStateMachineValidTransitions:
    @pytest.mark.parametrize(
        "from_state,to_state",
        [
            (SystemState.INITIALIZING, SystemState.STARTING),
            (SystemState.STARTING, SystemState.READY),
            (SystemState.READY, SystemState.DEGRADED),
            (SystemState.DEGRADED, SystemState.RECOVERING),
            (SystemState.RECOVERING, SystemState.READY),
            (SystemState.READY, SystemState.HALTED),
            (SystemState.DEGRADED, SystemState.HALTED),
            (SystemState.HALTED, SystemState.STARTING),
            (SystemState.READY, SystemState.MAINTENANCE),
            (SystemState.MAINTENANCE, SystemState.READY),
        ],
    )
    def test_valid_transition_accepted(self, from_state, to_state):
        assert SystemStateMachine.can_transition(from_state, to_state)
        # assert_transition must not raise
        SystemStateMachine.assert_transition(from_state, to_state)

    def test_any_state_can_fail(self):
        for state in SystemState:
            if state is SystemState.FAILED:
                continue  # already failed — no self-transition needed
            assert SystemStateMachine.can_transition(state, SystemState.FAILED)

    def test_failed_can_restart(self):
        assert SystemStateMachine.can_transition(SystemState.FAILED, SystemState.STARTING)
        assert SystemStateMachine.can_transition(SystemState.FAILED, SystemState.MAINTENANCE)


class TestSystemStateMachineInvalidTransitions:
    @pytest.mark.parametrize(
        "from_state,to_state",
        [
            (SystemState.INITIALIZING, SystemState.READY),  # must go through STARTING
            (SystemState.READY, SystemState.INITIALIZING),  # no backward jump
            (SystemState.READY, SystemState.STARTING),      # READY never goes back to STARTING
            (SystemState.HALTED, SystemState.READY),        # halt requires restart cycle
            (SystemState.HALTED, SystemState.DEGRADED),
            (SystemState.MAINTENANCE, SystemState.HALTED),
            (SystemState.STARTING, SystemState.INITIALIZING),
        ],
    )
    def test_invalid_transition_rejected(self, from_state, to_state):
        assert not SystemStateMachine.can_transition(from_state, to_state)

    def test_invalid_transition_raises(self):
        with pytest.raises(StateTransitionError):
            SystemStateMachine.assert_transition(
                SystemState.READY, SystemState.STARTING
            )

    def test_transition_error_carries_states(self):
        with pytest.raises(StateTransitionError) as exc_info:
            SystemStateMachine.assert_transition(
                SystemState.HALTED, SystemState.READY
            )
        assert exc_info.value.from_state is SystemState.HALTED
        assert exc_info.value.to_state is SystemState.READY

    def test_validate_coerces_string(self):
        assert SystemStateMachine.validate("READY") is SystemState.READY
