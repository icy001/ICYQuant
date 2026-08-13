"""Tests for Default Deny semantics (Commit 28 Part 1.2, sections 16, 25, 30)."""

from services.governance.decision import (
    DecisionEffect,
    GovernanceContext,
    GovernanceEngine,
)
from services.governance.models import Principal
from services.governance.permission import Permission
from services.governance.policy import Policy
from services.governance.registry import GovernanceRegistry, build_standard_governance
from services.governance.role import Role


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


def _engine():
    registry = build_standard_governance()
    registry.register_principal(Principal("ops-001", "production-operator", "USER"))
    registry.register_principal(Principal("observer-001", "observer", "USER"))
    return GovernanceEngine(registry)


def test_default_deny_unknown_principal():
    engine = GovernanceEngine(build_standard_governance())

    decision = engine.evaluate(_context(principal_id="unknown", role_ids=()))

    assert decision.effect == DecisionEffect.DENY


def test_default_deny_missing_permission():
    """Spec section 29 — OBSERVER cannot kill trading."""
    engine = _engine()

    decision = engine.evaluate(
        _context(
            principal_id="observer-001",
            role_ids=("OBSERVER",),
            action="kill",
        )
    )

    assert decision.effect == DecisionEffect.DENY
    assert decision.reason == "permission denied"


def test_default_deny_no_matching_policy():
    """Spec section 30 — permission alone does not authorise."""
    registry = GovernanceRegistry()
    registry.register_principal(Principal("ops-001", "production-operator", "USER"))
    registry.register_role(Role("OPERATOR", "Operator", "Handles incidents."))
    registry.register_permission(Permission("trading:pause", "trading", "pause"))
    registry.assign_permission_to_role("OPERATOR", "trading:pause")
    engine = GovernanceEngine(registry)

    decision = engine.evaluate(_context())

    assert decision.effect == DecisionEffect.DENY
    assert decision.reason == "no policy matched"


def test_default_deny_non_production_pause():
    """Standard PAUSE-BLOCKED policy denies pause outside production."""
    engine = _engine()

    decision = engine.evaluate(_context(environment="staging"))

    assert decision.effect == DecisionEffect.DENY
    assert decision.policy_id == "POLICY-TRADING-PAUSE-BLOCKED-001"


def test_default_deny_inactive_principal():
    registry = GovernanceRegistry()
    registry.register_principal(
        Principal("ops-001", "production-operator", "USER", active=False)
    )
    engine = GovernanceEngine(registry)

    decision = engine.evaluate(_context())

    assert decision.effect == DecisionEffect.DENY
    assert decision.reason == "principal inactive"


class _BrokenRegistry(GovernanceRegistry):
    def get_principal(self, principal_id):
        raise RuntimeError("policy store unavailable")


def test_fail_closed_on_engine_error():
    engine = GovernanceEngine(_BrokenRegistry())

    decision = engine.evaluate(_context())

    assert decision.effect == DecisionEffect.DENY
    assert decision.reason == "governance failure: fail closed"
