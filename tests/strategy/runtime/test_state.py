"""Tests for the strategy runtime state enum."""

from __future__ import annotations

from services.strategy.runtime.state import (
    ALIVE_STATES,
    HEALTHY_STATES,
    UNKNOWN_STATES,
    RuntimeState,
    runtime_state_value,
)


class TestRuntimeStateValues:
    def test_all_spec_states_exist(self) -> None:
        expected = {
            "UNKNOWN",
            "INITIALIZING",
            "READY",
            "RUNNING",
            "DEGRADED",
            "STOPPING",
            "STOPPED",
            "FAILED",
        }
        assert {state.value for state in RuntimeState} == expected

    def test_str_enum_comparison(self) -> None:
        assert RuntimeState.RUNNING == "RUNNING"
        assert RuntimeState.UNKNOWN.value == "UNKNOWN"

    def test_normalise_accepts_enum_and_string(self) -> None:
        assert runtime_state_value(RuntimeState.RUNNING) == "RUNNING"
        assert runtime_state_value("DEGRADED") == "DEGRADED"


class TestRuntimeStateGroups:
    def test_alive_states(self) -> None:
        assert "RUNNING" in ALIVE_STATES
        assert "READY" in ALIVE_STATES
        assert "STOPPED" not in ALIVE_STATES
        assert "UNKNOWN" not in ALIVE_STATES

    def test_healthy_states(self) -> None:
        assert "READY" in HEALTHY_STATES
        assert "RUNNING" in HEALTHY_STATES
        assert "DEGRADED" not in HEALTHY_STATES

    def test_unknown_states(self) -> None:
        assert "UNKNOWN" in UNKNOWN_STATES
