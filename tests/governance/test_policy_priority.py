"""Tests for policy priority / conflict resolution (Commit 28 Part 1.2, sections 14-15, 26-28)."""

from services.governance.decision import (
    DecisionEffect,
    GovernanceContext,
    GovernanceEngine,
)
from services.governance.models import Principal
from services.governance.permission import Permission
from services.governance.policy import Policy
from services.governance.registry import GovernanceRegistry
from services.governance.role import Role


def _registry():
    registry = GovernanceRegistry()
    registry.register_principal(Principal("ops-001", "production-operator", "USER"))
    registry.register_role(Role("OPERATOR", "Operator", "Handles incidents."))
    registry.register_permission(Permission("trading:pause", "trading", "pause"))
    registry.assign_permission_to_role("OPERATOR", "trading:pause")
    return registry


def _context(**overrides):
    base = dict(
        principal_id="ops-001",
        role_ids=("OPERATOR",),
        resource="trading",
        action="pause",
        environment="production",
    )
    base.update(overrides)
    return GovernanceContext(**base)


def test_highest_priority_policy_wins():
    """Spec section 14/35 — smaller priority number wins."""
    registry = _registry()
    registry.register_policy(
        Policy("POLICY-LOW", "Default Allow", "trading", "pause", priority=100)
    )
    registry.register_policy(
        Policy("POLICY-HIGH", "Emergency Allow", "trading", "pause", priority=10)
    )
    engine = GovernanceEngine(registry)

    decision = engine.evaluate(_context())

    assert decision.effect == DecisionEffect.ALLOW
    assert decision.policy_id == "POLICY-HIGH"


def test_explicit_deny_overrides_allow():
    """Spec section 15/33 — DENY beats ALLOW regardless of priority."""
    registry = _registry()
    registry.register_policy(
        Policy("POLICY-ALLOW", "Default Allow", "trading", "pause", priority=100, effect="ALLOW")
    )
    registry.register_policy(
        Policy("POLICY-DENY", "Explicit Deny", "trading", "pause", priority=20, effect="DENY")
    )
    engine = GovernanceEngine(registry)

    decision = engine.evaluate(_context())

    assert decision.effect == DecisionEffect.DENY
    assert decision.policy_id == "POLICY-DENY"


def test_require_approval_beats_allow():
    """Spec section 26 — REQUIRE_APPROVAL > ALLOW."""
    registry = _registry()
    registry.register_policy(
        Policy("POLICY-ALLOW", "Default Allow", "trading", "pause", priority=100, effect="ALLOW")
    )
    registry.register_policy(
        Policy(
            "POLICY-APPROVAL",
            "Require Approval",
            "trading",
            "pause",
            priority=50,
            effect="REQUIRE_APPROVAL",
            requires_approval=True,
        )
    )
    engine = GovernanceEngine(registry)

    decision = engine.evaluate(_context())

    assert decision.effect == DecisionEffect.REQUIRE_APPROVAL
    assert decision.policy_id == "POLICY-APPROVAL"
    assert decision.approval_required


def test_deny_beats_require_approval():
    """Spec section 26 — DENY > REQUIRE_APPROVAL > ALLOW."""
    registry = _registry()
    registry.register_policy(
        Policy(
            "POLICY-APPROVAL",
            "Require Approval",
            "trading",
            "pause",
            priority=50,
            effect="REQUIRE_APPROVAL",
            requires_approval=True,
        )
    )
    registry.register_policy(
        Policy("POLICY-DENY", "Explicit Deny", "trading", "pause", priority=100, effect="DENY")
    )
    engine = GovernanceEngine(registry)

    decision = engine.evaluate(_context())

    assert decision.effect == DecisionEffect.DENY
    assert decision.policy_id == "POLICY-DENY"


def test_same_priority_tie_broken_by_policy_id():
    """Spec section 28 — stable policy_id tie-breaker for determinism."""
    registry = _registry()
    registry.register_policy(
        Policy("POLICY-B", "Second", "trading", "pause", priority=50)
    )
    registry.register_policy(
        Policy("POLICY-A", "First", "trading", "pause", priority=50)
    )
    engine = GovernanceEngine(registry)

    decision = engine.evaluate(_context())

    assert decision.policy_id == "POLICY-A"


def test_evaluation_is_deterministic():
    """Spec section 34 — same context always yields the same decision."""
    registry = _registry()
    registry.register_policy(
        Policy("POLICY-1", "First", "trading", "pause", priority=50)
    )
    registry.register_policy(
        Policy("POLICY-2", "Second", "trading", "pause", priority=50)
    )
    engine = GovernanceEngine(registry)

    context = _context()
    first = engine.evaluate(context)
    second = engine.evaluate(context)

    assert first == second


def test_disabled_policy_is_ignored():
    registry = _registry()
    registry.register_policy(
        Policy(
            "POLICY-OFF",
            "Disabled Deny",
            "trading",
            "pause",
            priority=10,
            effect="DENY",
            enabled=False,
        )
    )
    registry.register_policy(
        Policy("POLICY-ON", "Default Allow", "trading", "pause", priority=100)
    )
    engine = GovernanceEngine(registry)

    decision = engine.evaluate(_context())

    assert decision.effect == DecisionEffect.ALLOW
    assert decision.policy_id == "POLICY-ON"
