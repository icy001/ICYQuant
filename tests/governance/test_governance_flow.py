"""End-to-end governance flows on the standard policy set (Commit 28 Part 1.2).

Covers the production scenarios of spec sections 20-24:
  - Production pause: WARNING -> ALLOW, CRITICAL -> REQUIRE_APPROVAL
  - Non-production pause -> DENY
  - Recovery-aware resume: incomplete recovery -> DENY, complete -> ALLOW
  - Emergency kill: CONTROL_OPERATOR + EMERGENCY -> ALLOW
  - Separation of duties: Administrator cannot execute trading controls
"""

from services.governance.decision import (
    DecisionEffect,
    GovernanceContext,
    GovernanceEngine,
)
from services.governance.models import Principal
from services.governance.registry import build_standard_governance


def _engine():
    registry = build_standard_governance()
    registry.register_principal(Principal("ops-001", "production-operator", "USER"))
    registry.register_principal(
        Principal("ctrl-001", "control-operator", "USER")
    )
    registry.register_principal(
        Principal("admin-001", "administrator", "USER")
    )
    return GovernanceEngine(registry)


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


def test_production_pause_critical_requires_approval():
    """Spec sections 21/32 — CRITICAL production pause is REQUIRE_APPROVAL."""
    engine = _engine()

    decision = engine.evaluate(
        _context(severity="CRITICAL", incident_id="INC-001")
    )

    assert decision.effect == DecisionEffect.REQUIRE_APPROVAL
    assert decision.approval_required
    assert decision.policy_id == "POLICY-TRADING-PAUSE-001"


def test_production_pause_warning_allows():
    """Non-critical production pause follows the default allow policy."""
    engine = _engine()

    decision = engine.evaluate(_context(severity="WARNING"))

    assert decision.effect == DecisionEffect.ALLOW
    assert decision.policy_id == "POLICY-TRADING-PAUSE-DEFAULT-001"


def test_non_production_pause_denied():
    engine = _engine()

    decision = engine.evaluate(
        _context(environment="staging", severity="CRITICAL")
    )

    assert decision.effect == DecisionEffect.DENY
    assert decision.policy_id == "POLICY-TRADING-PAUSE-BLOCKED-001"


def test_resume_denied_when_recovery_not_ready():
    """Spec section 23 — incomplete recovery blocks resume."""
    engine = _engine()

    decision = engine.evaluate(
        _context(
            principal_id="ctrl-001",
            role_ids=("CONTROL_OPERATOR",),
            action="resume",
            severity="CRITICAL",
            recovery_status="MITIGATING",
            reconciliation_status="PENDING",
        )
    )

    assert decision.effect == DecisionEffect.DENY


def test_resume_denied_without_approval():
    """Spec section 22 — resume requires an approval present."""
    engine = _engine()

    decision = engine.evaluate(
        _context(
            principal_id="ctrl-001",
            role_ids=("CONTROL_OPERATOR",),
            action="resume",
            severity="CRITICAL",
            recovery_status="READY",
            reconciliation_status="PASSED",
        )
    )

    assert decision.effect == DecisionEffect.DENY


def test_resume_allowed_when_recovery_complete():
    """Full recovery + reconciliation + approval -> ALLOW."""
    engine = _engine()

    decision = engine.evaluate(
        _context(
            principal_id="ctrl-001",
            role_ids=("CONTROL_OPERATOR",),
            action="resume",
            severity="CRITICAL",
            incident_id="INC-001",
            approval_id="APR-001",
            recovery_status="READY",
            reconciliation_status="PASSED",
            risk_status="PASSED",
        )
    )

    assert decision.effect == DecisionEffect.ALLOW
    assert decision.policy_id == "POLICY-TRADING-RESUME-001"


def test_emergency_kill_allows_control_operator_in_emergency():
    """Spec section 24 — CONTROL_OPERATOR + EMERGENCY -> ALLOW."""
    engine = _engine()

    decision = engine.evaluate(
        _context(
            principal_id="ctrl-001",
            role_ids=("CONTROL_OPERATOR",),
            action="kill",
            severity="EMERGENCY",
            incident_id="INC-999",
        )
    )

    assert decision.effect == DecisionEffect.ALLOW
    assert decision.policy_id == "POLICY-TRADING-KILL-001"


def test_emergency_kill_denied_without_emergency_severity():
    engine = _engine()

    decision = engine.evaluate(
        _context(
            principal_id="ctrl-001",
            role_ids=("CONTROL_OPERATOR",),
            action="kill",
            severity="CRITICAL",
        )
    )

    assert decision.effect == DecisionEffect.DENY


def test_emergency_kill_denied_for_plain_operator():
    engine = _engine()

    decision = engine.evaluate(_context(action="kill", severity="EMERGENCY"))

    assert decision.effect == DecisionEffect.DENY
    assert decision.reason == "permission denied"


def test_failover_requires_control_operator():
    engine = _engine()

    assert (
        engine.evaluate(
            _context(
                principal_id="ctrl-001",
                role_ids=("CONTROL_OPERATOR",),
                action="failover",
                severity="CRITICAL",
            )
        ).effect
        == DecisionEffect.ALLOW
    )

    assert (
        engine.evaluate(
            _context(action="failover", severity="CRITICAL")
        ).effect
        == DecisionEffect.DENY
    )


def test_administrator_cannot_pause_trading():
    """Separation of duties: Administrator is not a Control Operator."""
    engine = _engine()

    decision = engine.evaluate(
        _context(
            principal_id="admin-001",
            role_ids=("ADMINISTRATOR",),
            action="pause",
            severity="CRITICAL",
        )
    )

    assert decision.effect == DecisionEffect.DENY
    assert decision.reason == "permission denied"
