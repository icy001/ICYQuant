"""Tests for VenueState (Commit 26 Part 1.4, spec section 7)."""

from services.control_plane.venue import VenueState


def test_enum_members_and_values():
    """VenueState exposes the six documented states."""
    assert {s.value for s in VenueState} == {
        "ONLINE",
        "DEGRADED",
        "PAUSED",
        "DISABLED",
        "FAILOVER",
        "UNKNOWN",
    }


def test_str_enum_value():
    assert str(VenueState.DISABLED) == "VenueState.DISABLED"
    assert VenueState.DISABLED.value == "DISABLED"


def test_from_value_roundtrip():
    for state in VenueState:
        assert VenueState(state.value) is state
