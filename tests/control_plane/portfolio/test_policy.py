"""Tests for PortfolioControlPolicy (Commit 26 Part 1.3, spec section 12)."""

import pytest

from services.control_plane.portfolio import PortfolioControlPolicy


def test_default_policy():
    policy = PortfolioControlPolicy()
    assert policy.restricted_allow_new_risk is False
    assert policy.restricted_allow_new_orders is False
    assert policy.restricted_allow_reduce is True
    assert policy.reduce_only_allow_reduce is True
    assert policy.frozen_allow_reduce is True
    assert policy.liquidating_allow_reduce is True


def test_policy_is_frozen():
    with pytest.raises(Exception):
        PortfolioControlPolicy().frozen_allow_reduce = False  # type: ignore[misc]


def test_custom_policy():
    policy = PortfolioControlPolicy(
        restricted_allow_new_risk=True,
        frozen_allow_reduce=False,
    )
    assert policy.restricted_allow_new_risk is True
    assert policy.frozen_allow_reduce is False
