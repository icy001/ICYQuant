"""Tests for GlobalControlState (Commit 26 Part 1.5, spec section 3)."""

from services.control_plane.global_control import GlobalControlState


def test_enum_members_and_values():
    """GlobalControlState exposes the four documented states."""
    assert {s.value for s in GlobalControlState} == {
        "NORMAL",
        "RESTRICTED",
        "KILLED",
        "RECOVERY",
    }


def test_str_enum_value():
    assert str(GlobalControlState.KILLED) == (
        "GlobalControlState.KILLED"
    )
    assert GlobalControlState.KILLED.value == "KILLED"


def test_from_value_roundtrip():
    for state in GlobalControlState:
        assert GlobalControlState(state.value) is state
