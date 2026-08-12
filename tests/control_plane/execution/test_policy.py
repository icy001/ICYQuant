"""Tests for ExecutionControlPolicy (Commit 26 Part 1.4, spec section 5)."""

import pytest

from services.control_plane.execution import ExecutionControlPolicy


def test_default_policy():
    policy = ExecutionControlPolicy()
    assert policy.degraded_allow_new is True
    assert policy.paused_allow_cancel is True
    assert policy.paused_allow_reduce is True
    assert policy.draining_allow_cancel is True
    assert policy.draining_allow_reduce is True
    assert policy.disabled_allow_cancel is True
    assert policy.disabled_allow_emergency_flatten is True


def test_policy_is_frozen():
    with pytest.raises(Exception):
        ExecutionControlPolicy().paused_allow_cancel = False  # type: ignore[misc]


def test_custom_policy():
    policy = ExecutionControlPolicy(
        degraded_allow_new=False,
        disabled_allow_emergency_flatten=False,
    )
    assert policy.degraded_allow_new is False
    assert policy.disabled_allow_emergency_flatten is False
