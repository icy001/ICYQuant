"""Tests for StrategyState (Commit 26 Part 1.3, spec section 3)."""

from services.control_plane.strategy import StrategyState


def test_enum_members_and_values():
    """StrategyState exposes the five documented states."""
    assert {s.value for s in StrategyState} == {
        "RUNNING",
        "PAUSED",
        "DISABLED",
        "DRAINING",
        "RECOVERING",
    }


def test_str_enum_value():
    assert str(StrategyState.PAUSED) == "StrategyState.PAUSED"
    assert StrategyState.PAUSED.value == "PAUSED"


def test_running_is_default_least_restrictive():
    assert StrategyState.RUNNING.value == "RUNNING"
    assert StrategyState.RUNNING.trading_capability == "signal+new+reduce"


def test_restrictive_states_are_reduce_only_or_blocked():
    for state in (
        StrategyState.PAUSED,
        StrategyState.DRAINING,
        StrategyState.DISABLED,
        StrategyState.RECOVERING,
    ):
        assert state.trading_capability == "reduce-only-or-blocked"


def test_from_value_roundtrip():
    for state in StrategyState:
        assert StrategyState(state.value) is state
