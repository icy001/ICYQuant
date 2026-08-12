"""Tests for VenueControlPolicy (Commit 26 Part 1.4, spec section 10)."""

import pytest

from services.control_plane.venue import VenueControlPolicy


def test_default_policy():
    policy = VenueControlPolicy()
    assert policy.degraded_allow_new is False
    assert policy.paused_allow_new is False
    assert policy.paused_allow_cancel is True
    assert policy.paused_allow_reduce is True
    assert policy.disabled_allow_cancel is True
    assert policy.disabled_allow_reduce is False
    assert policy.disabled_allow_emergency_flatten is True


def test_policy_is_frozen():
    with pytest.raises(Exception):
        VenueControlPolicy().paused_allow_cancel = False  # type: ignore[misc]


def test_custom_policy():
    policy = VenueControlPolicy(
        degraded_allow_new=True,
        disabled_allow_reduce=True,
    )
    assert policy.degraded_allow_new is True
    assert policy.disabled_allow_reduce is True
