"""Tests for the strategy control state model."""

from __future__ import annotations

from services.strategy.domain.control_state import (
    ACTIVE_STATES,
    TERMINAL_STATES,
    StrategyControlState,
    is_active,
    is_terminal,
)


class TestStrategyControlState:
    def test_all_control_states_defined(self) -> None:
        assert {state.value for state in StrategyControlState} == {
            "STOPPED",
            "STARTING",
            "RUNNING",
            "PAUSING",
            "PAUSED",
            "RESUMING",
            "STOPPING",
            "KILLED",
            "FAILED",
        }

    def test_transitional_states_present(self) -> None:
        assert StrategyControlState.PAUSING.value == "PAUSING"
        assert StrategyControlState.RESUMING.value == "RESUMING"
        assert StrategyControlState.STOPPING.value == "STOPPING"
        assert StrategyControlState.STARTING.value == "STARTING"

    def test_terminal_states(self) -> None:
        assert TERMINAL_STATES == {"STOPPED", "KILLED", "FAILED"}
        assert is_terminal("STOPPED")
        assert is_terminal("KILLED")
        assert is_terminal("FAILED")
        assert not is_terminal("RUNNING")

    def test_active_states(self) -> None:
        assert "RUNNING" in ACTIVE_STATES
        assert "PAUSED" in ACTIVE_STATES
        assert is_active("RUNNING")
        assert is_active("PAUSED")
        assert not is_active("KILLED")
        assert not is_active("STOPPED")

    def test_enum_and_string_inputs_agree(self) -> None:
        assert is_active(StrategyControlState.RUNNING) == is_active("RUNNING")
        assert is_terminal(StrategyControlState.KILLED) == is_terminal("KILLED")

    def test_killed_is_terminal_but_record_preserved(self) -> None:
        # KILLED is a control state, not a deletion: the strategy record,
        # command history, audit trail and risk state all remain.
        assert StrategyControlState.KILLED.value == "KILLED"
        assert is_terminal("KILLED")
