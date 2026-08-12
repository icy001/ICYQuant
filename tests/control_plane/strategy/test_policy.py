"""Tests for StrategyControlPolicy (Commit 26 Part 1.3, spec section 5)."""

import pytest

from services.control_plane.strategy import StrategyControlPolicy


def test_default_policy():
    policy = StrategyControlPolicy()
    assert policy.paused_allow_reduce is True
    assert policy.draining_allow_reduce is True
    assert policy.disabled_allow_reduce is True
    assert policy.disabled_allow_signal is False


def test_policy_is_frozen():
    with pytest.raises(Exception):
        StrategyControlPolicy().paused_allow_reduce = False  # type: ignore[misc]


def test_custom_policy():
    policy = StrategyControlPolicy(
        paused_allow_reduce=False,
        disabled_allow_signal=True,
    )
    assert policy.paused_allow_reduce is False
    assert policy.disabled_allow_signal is True
