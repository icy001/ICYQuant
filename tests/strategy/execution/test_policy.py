"""Tests for the strategy-level execution policy."""

import pytest

from services.strategy.execution.intent import SUPPORTED_EXECUTION_POLICIES
from services.strategy.execution.policy import ExecutionPolicy


def test_default_policy_allows_all_supported_policies() -> None:
    policy = ExecutionPolicy()
    assert set(policy.allowed_policies) == set(SUPPORTED_EXECUTION_POLICIES)


def test_policy_restricts_allowed_policies() -> None:
    policy = ExecutionPolicy(allowed_policies=frozenset({"MARKET", "LIMIT"}))
    assert policy.allows_policy("MARKET") is True
    assert policy.allows_policy("LIMIT") is True
    assert policy.allows_policy("TWAP") is False


def test_unsupported_policy_rejected() -> None:
    with pytest.raises(ValueError):
        ExecutionPolicy(allowed_policies=frozenset({"IOC"}))


def test_empty_allowed_policies_rejected() -> None:
    with pytest.raises(ValueError):
        ExecutionPolicy(allowed_policies=frozenset())


def test_max_intent_quantity_enforced() -> None:
    policy = ExecutionPolicy(max_intent_quantity=1000.0)
    assert policy.allows_quantity(500.0) is True
    assert policy.allows_quantity(1000.0) is True
    assert policy.allows_quantity(1000.5) is False
    assert policy.allows_quantity(0) is False
    assert policy.allows_quantity(-1) is False


def test_zero_max_intent_quantity_blocks_everything() -> None:
    # a policy without a positive limit may never express any intent
    policy = ExecutionPolicy()
    assert policy.allows_quantity(1.0) is False


def test_negative_max_intent_quantity_rejected() -> None:
    with pytest.raises(ValueError):
        ExecutionPolicy(max_intent_quantity=-1.0)


def test_negative_ttl_rejected() -> None:
    with pytest.raises(ValueError):
        ExecutionPolicy(intent_ttl_seconds=-1.0)


def test_ttl_seconds_uses_policy_value() -> None:
    policy = ExecutionPolicy(intent_ttl_seconds=5.0)
    assert policy.ttl_seconds() == 5.0
    assert policy.ttl_seconds(default=2.0) == 5.0


def test_zero_ttl_disables_expiry() -> None:
    policy = ExecutionPolicy(intent_ttl_seconds=0.0)
    assert policy.ttl_seconds() == 0.0


def test_allow_degraded_readiness_default_false() -> None:
    assert ExecutionPolicy().allow_degraded_readiness is False
    assert (
        ExecutionPolicy(allow_degraded_readiness=True).allow_degraded_readiness
        is True
    )
