"""Tests for PortfolioState (Commit 26 Part 1.3, spec section 10)."""

from services.control_plane.portfolio import PortfolioState


def test_enum_members_and_values():
    """PortfolioState exposes the six documented states."""
    assert {s.value for s in PortfolioState} == {
        "ACTIVE",
        "RESTRICTED",
        "REDUCE_ONLY",
        "FROZEN",
        "LIQUIDATING",
        "RECOVERING",
    }


def test_str_enum_value():
    assert str(PortfolioState.FROZEN) == "PortfolioState.FROZEN"
    assert PortfolioState.FROZEN.value == "FROZEN"


def test_risk_reduction_stage_ordering():
    """Higher stage = more restrictive posture."""
    assert (
        PortfolioState.ACTIVE.risk_reduction_stage
        < PortfolioState.RESTRICTED.risk_reduction_stage
        < PortfolioState.REDUCE_ONLY.risk_reduction_stage
        < PortfolioState.FROZEN.risk_reduction_stage
        < PortfolioState.LIQUIDATING.risk_reduction_stage
    )


def test_from_value_roundtrip():
    for state in PortfolioState:
        assert PortfolioState(state.value) is state
