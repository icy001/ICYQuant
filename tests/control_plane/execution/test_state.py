"""Tests for ExecutionState (Commit 26 Part 1.4, spec section 3)."""

from services.control_plane.execution import ExecutionState


def test_enum_members_and_values():
    """ExecutionState exposes the six documented states."""
    assert {s.value for s in ExecutionState} == {
        "ACTIVE",
        "DEGRADED",
        "PAUSED",
        "DISABLED",
        "DRAINING",
        "FAILOVER",
    }


def test_str_enum_value():
    assert str(ExecutionState.PAUSED) == "ExecutionState.PAUSED"
    assert ExecutionState.PAUSED.value == "PAUSED"


def test_from_value_roundtrip():
    for state in ExecutionState:
        assert ExecutionState(state.value) is state
