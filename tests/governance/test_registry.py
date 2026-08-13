"""Tests for services.governance.registry (Commit 28 Part 1.1)."""

from services.governance.models import Principal
from services.governance.permission import Permission
from services.governance.policy import Policy
from services.governance.registry import (
    GovernanceRegistry,
    build_standard_governance,
    build_standard_policies,
    register_standard_governance,
)
from services.governance.role import Role


def test_register_role():
    registry = GovernanceRegistry()
    role = Role("OPERATOR", "Operator", "Handles incidents.")
    registry.register_role(role)

    assert registry.roles["OPERATOR"] == role
    assert registry.get_role("OPERATOR") is role
    assert registry.get_role("UNKNOWN") is None


def test_register_permission():
    registry = GovernanceRegistry()
    permission = Permission("trading:pause", "trading", "pause")
    registry.register_permission(permission)

    assert registry.permissions["trading:pause"] == permission
    assert registry.get_permission("trading:pause") is permission


def test_register_policy():
    registry = GovernanceRegistry()
    policy = Policy("POLICY-001", "Trading Pause", "trading", "pause", priority=50)
    registry.register_policy(policy)

    assert registry.policies["POLICY-001"] == policy
    assert registry.get_policy("POLICY-001") is policy


def test_register_principal():
    registry = GovernanceRegistry()
    principal = Principal("ops-001", "production-operator", "USER")
    registry.register_principal(principal)

    assert registry.principals["ops-001"] == principal
    assert registry.get_principal("ops-001") is principal


def test_assign_permission_to_role():
    registry = GovernanceRegistry()
    registry.register_role(Role("OPERATOR", "Operator", "Handles incidents."))
    registry.assign_permission_to_role("OPERATOR", "incident:update")
    registry.assign_permission_to_role("OPERATOR", "runbook:execute")

    assert registry.permissions_for_role("OPERATOR") == (
        "incident:update",
        "runbook:execute",
    )
    assert registry.permissions_for_role("UNKNOWN") == ()


def test_build_standard_governance():
    registry = build_standard_governance()

    assert len(registry.roles) == 7
    assert len(registry.permissions) == 18
    assert len(registry.policies) == 6

    assert registry.get_policy("POLICY-TRADING-KILL-001") is not None
    assert registry.get_policy("POLICY-TRADING-PAUSE-001") is not None
    assert registry.get_policy("POLICY-TRADING-PAUSE-BLOCKED-001") is not None
    assert registry.get_policy("POLICY-TRADING-PAUSE-DEFAULT-001") is not None
    assert registry.get_policy("POLICY-TRADING-RESUME-001") is not None
    assert registry.get_policy("POLICY-TRADING-FAILOVER-001") is not None


def test_register_standard_governance_into_existing_registry():
    registry = GovernanceRegistry()
    register_standard_governance(registry)

    assert len(registry.roles) == 7
    assert len(registry.permissions) == 18


def test_control_operator_has_trading_kill_qualification():
    registry = build_standard_governance()
    control_operator_permissions = set(registry.permissions_for_role("CONTROL_OPERATOR"))

    assert {"trading:pause", "trading:resume", "trading:failover", "trading:kill"} <= control_operator_permissions


def test_role_separation_administrator_is_not_control_operator():
    """Spec section 7 — Administrator does not automatically equal Control Operator."""
    registry = build_standard_governance()
    administrator_permissions = set(registry.permissions_for_role("ADMINISTRATOR"))

    assert "policy:update" in administrator_permissions
    assert "role:update" in administrator_permissions
    assert not (administrator_permissions & {"trading:pause", "trading:kill", "trading:resume"})


def test_standard_policies_priorities():
    policies = build_standard_policies()
    priorities = {policy.policy_id: policy.priority for policy in policies}

    assert priorities["POLICY-TRADING-KILL-001"] == 10
    assert priorities["POLICY-TRADING-PAUSE-001"] == 50
    assert priorities["POLICY-TRADING-RESUME-001"] == 50
    assert priorities["POLICY-TRADING-FAILOVER-001"] == 50
