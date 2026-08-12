"""Tests for RoutingPolicy (Commit 26 Part 1.4, spec section 14)."""

import pytest

from services.control_plane.routing import RoutingPolicy


def test_default_policy():
    policy = RoutingPolicy()
    assert policy.enable_failover is True
    assert policy.allow_cross_venue_routing is True
    assert policy.require_healthy_venue is True


def test_policy_is_frozen():
    with pytest.raises(Exception):
        RoutingPolicy().enable_failover = False  # type: ignore[misc]


def test_custom_policy():
    policy = RoutingPolicy(
        enable_failover=False,
        allow_cross_venue_routing=False,
    )
    assert policy.enable_failover is False
    assert policy.allow_cross_venue_routing is False
