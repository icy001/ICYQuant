"""
Tests for the Recovery gate state machine (Commit 26 Part 1.5, spec section 12).

注意：这是 Part 1.5 恢复门控状态机（IDLE/VALIDATING/.../COMPLETED），
与 Commit 24 的 recovery.recovery_state.RecoveryState 不同。
"""

from services.control_plane.recovery.state import RecoveryState


def test_enum_members_and_values():
    """RecoveryState exposes the eight documented states."""
    assert {s.value for s in RecoveryState} == {
        "IDLE",
        "VALIDATING",
        "BLOCKED",
        "APPROVAL_REQUIRED",
        "APPROVED",
        "RESUMING",
        "COMPLETED",
        "FAILED",
    }


def test_str_enum_value():
    assert str(RecoveryState.APPROVED) == "RecoveryState.APPROVED"
    assert RecoveryState.APPROVED.value == "APPROVED"


def test_from_value_roundtrip():
    for state in RecoveryState:
        assert RecoveryState(state.value) is state
