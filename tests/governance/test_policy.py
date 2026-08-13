"""Tests for services.governance.policy — permission-style Policy (Commit 28 Part 1.1)."""

from dataclasses import FrozenInstanceError

import pytest

from services.governance.policy import Policy
from services.governance.registry import GovernanceRegistry


def test_policy_defaults():
    policy = Policy(
        policy_id="POLICY-001",
        name="Trading Pause",
        resource="trading",
        action="pause",
    )
    assert policy.enabled is True
    assert policy.priority == 100


def test_policy_construction_with_priority():
    policy = Policy(
        policy_id="POLICY-TRADING-KILL-001",
        name="Emergency Trading Kill",
        resource="trading",
        action="kill",
        priority=10,
    )
    assert policy.priority == 10


def test_policy_is_frozen():
    policy = Policy("POLICY-001", "Trading Pause", "trading", "pause")
    with pytest.raises(FrozenInstanceError):
        policy.enabled = False  # type: ignore[misc]


def test_policy_registry():
    """Spec section 33 — policy registration."""
    registry = GovernanceRegistry()

    policy = Policy(
        policy_id="POLICY-001",
        name="Trading Pause",
        resource="trading",
        action="pause",
    )

    registry.register_policy(policy)

    assert registry._policies["POLICY-001"] == policy  # noqa: SLF001
    assert registry.get_policy("POLICY-001") is policy


def test_policies_for_sorted_by_priority():
    registry = GovernanceRegistry()
    registry.register_policy(
        Policy("POLICY-50", "Production Control", "trading", "pause", priority=50)
    )
    registry.register_policy(
        Policy("POLICY-10", "Emergency Policy", "trading", "pause", priority=10)
    )

    policies = registry.policies_for("trading", "pause")

    assert [policy.policy_id for policy in policies] == ["POLICY-10", "POLICY-50"]


def test_policies_for_excludes_disabled():
    registry = GovernanceRegistry()
    registry.register_policy(
        Policy("POLICY-ON", "Enabled Policy", "trading", "pause", priority=50)
    )
    registry.register_policy(
        Policy("POLICY-OFF", "Disabled Policy", "trading", "pause", priority=10, enabled=False)
    )

    policies = registry.policies_for("trading", "pause")

    assert [policy.policy_id for policy in policies] == ["POLICY-ON"]


def test_policies_for_filters_by_resource_and_action():
    registry = GovernanceRegistry()
    registry.register_policy(
        Policy("POLICY-PAUSE", "Trading Pause", "trading", "pause", priority=50)
    )
    registry.register_policy(
        Policy("POLICY-KILL", "Trading Kill", "trading", "kill", priority=10)
    )

    assert registry.policies_for("trading", "pause") == (
        registry.get_policy("POLICY-PAUSE"),
    )
    assert registry.policies_for("trading", "kill") == (
        registry.get_policy("POLICY-KILL"),
    )
    assert registry.policies_for("trading", "resume") == ()
