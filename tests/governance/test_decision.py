"""Tests for services.governance.decision (Commit 28 Part 1.1)."""

from services.governance.decision import (
    DecisionEffect,
    GovernanceContext,
    GovernanceDecision,
    GovernanceEngine,
)
from services.governance.models import Principal
from services.governance.permission import Permission
from services.governance.policy import Policy
from services.governance.registry import GovernanceRegistry
from services.governance.role import Role


def test_require_approval():
    """Spec section 32 — decision model supports REQUIRE_APPROVAL."""
    decision = GovernanceDecision(
        effect=DecisionEffect.REQUIRE_APPROVAL,
        reason="critical action requires approval",
        policy_id="POLICY-001",
        approval_required=True,
    )

    assert decision.approval_required
    assert decision.effect == DecisionEffect.REQUIRE_APPROVAL


def test_default_deny():
    """Spec section 31 — unknown principal is denied by default."""
    engine = GovernanceEngine()

    context = GovernanceContext(
        principal_id="unknown",
        role_ids=(),
        resource="trading",
        action="kill",
        environment="production",
    )

    decision = engine.evaluate(context)

    assert decision.effect == DecisionEffect.DENY


def test_deny_when_principal_required():
    engine = GovernanceEngine()

    decision = engine.evaluate(
        GovernanceContext(
            principal_id="",
            role_ids=(),
            resource="trading",
            action="pause",
            environment="production",
        )
    )

    assert decision.effect == DecisionEffect.DENY
    assert decision.reason == "principal required"


def test_deny_when_principal_inactive():
    registry = GovernanceRegistry()
    registry.register_principal(
        Principal("ops-001", "production-operator", "USER", active=False)
    )
    engine = GovernanceEngine(registry)

    decision = engine.evaluate(
        GovernanceContext(
            principal_id="ops-001",
            role_ids=("OPERATOR",),
            resource="trading",
            action="pause",
            environment="production",
        )
    )

    assert decision.effect == DecisionEffect.DENY
    assert decision.reason == "principal inactive"


def test_deny_when_no_permission():
    registry = GovernanceRegistry()
    registry.register_principal(Principal("ops-001", "production-operator", "USER"))
    registry.register_role(Role("OPERATOR", "Operator", "Handles incidents."))
    registry.register_permission(Permission("trading:read", "trading", "read"))
    registry.assign_permission_to_role("OPERATOR", "trading:read")
    registry.register_policy(
        Policy("POLICY-PAUSE", "Trading Pause", "trading", "pause", priority=50)
    )
    engine = GovernanceEngine(registry)

    decision = engine.evaluate(
        GovernanceContext(
            principal_id="ops-001",
            role_ids=("OPERATOR",),
            resource="trading",
            action="pause",
            environment="production",
        )
    )

    assert decision.effect == DecisionEffect.DENY
    assert decision.reason == "permission denied"


def test_deny_when_no_policy_matched():
    """Permission alone is not authorization — no policy means DENY."""
    registry = GovernanceRegistry()
    registry.register_principal(Principal("ops-001", "production-operator", "USER"))
    registry.register_role(Role("OPERATOR", "Operator", "Handles incidents."))
    registry.register_permission(Permission("trading:pause", "trading", "pause"))
    registry.assign_permission_to_role("OPERATOR", "trading:pause")
    engine = GovernanceEngine(registry)

    decision = engine.evaluate(
        GovernanceContext(
            principal_id="ops-001",
            role_ids=("OPERATOR",),
            resource="trading",
            action="pause",
            environment="production",
        )
    )

    assert decision.effect == DecisionEffect.DENY
    assert decision.reason == "no policy matched"


def test_allow_when_fully_authorized():
    registry = GovernanceRegistry()
    registry.register_principal(Principal("ops-001", "production-operator", "USER"))
    registry.register_role(Role("OPERATOR", "Operator", "Handles incidents."))
    registry.register_permission(Permission("trading:pause", "trading", "pause"))
    registry.assign_permission_to_role("OPERATOR", "trading:pause")
    registry.register_policy(
        Policy("POLICY-PAUSE", "Trading Pause", "trading", "pause", priority=50)
    )
    engine = GovernanceEngine(registry)

    decision = engine.evaluate(
        GovernanceContext(
            principal_id="ops-001",
            role_ids=("OPERATOR",),
            resource="trading",
            action="pause",
            environment="production",
            incident_id="INC-001",
            severity="CRITICAL",
        )
    )

    assert decision.effect == DecisionEffect.ALLOW
    assert decision.reason == "policy matched"
    assert decision.policy_id == "POLICY-PAUSE"
    assert decision.approval_required is False


class _BrokenRegistry(GovernanceRegistry):
    def get_principal(self, principal_id):
        raise RuntimeError("policy store unavailable")


def test_fail_closed_on_engine_error():
    """Spec section 26 — governance failure must not ALLOW."""
    engine = GovernanceEngine(_BrokenRegistry())

    decision = engine.evaluate(
        GovernanceContext(
            principal_id="ops-001",
            role_ids=("OPERATOR",),
            resource="trading",
            action="pause",
            environment="production",
        )
    )

    assert decision.effect == DecisionEffect.DENY
    assert decision.reason == "governance failure: fail closed"


def test_governance_context_captures_who_what_where_why():
    context = GovernanceContext(
        principal_id="ops-001",
        role_ids=("OPERATOR",),
        resource="trading",
        action="pause",
        environment="production",
        incident_id="INC-001",
        severity="CRITICAL",
        approval_id="APR-001",
    )

    assert context.principal_id == "ops-001"
    assert context.role_ids == ("OPERATOR",)
    assert context.environment == "production"
    assert context.incident_id == "INC-001"
    assert context.severity == "CRITICAL"
    assert context.approval_id == "APR-001"
