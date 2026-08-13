"""Tests for governance re-evaluation after approval (Commit 28 Part 1.3).

Approved approval never bypasses the CURRENT governance policy:

    APPROVED -> RE-EVALUATE -> ALLOW -> CONSUME -> Control Plane

- 10:00 的 Approval 不能自动绕过 10:10 的 Governance Policy。
- Approval 是 single-use：消费后重放必须 DENY。
- Approval 绑定 resource / action / incident / requester / policy。
"""

from datetime import datetime, timedelta, timezone

import pytest

from services.governance.approval import (
    Approval,
    ApprovalState,
    approve,
    consume,
)
from services.governance.approval_engine import GovernanceApprovalEngine
from services.governance.approval_rule import ApprovalRule
from services.governance.audit import ApprovalAuditEventType
from services.governance.condition import ConditionOperator, PolicyCondition
from services.governance.decision import (
    DecisionEffect,
    GovernanceContext,
    GovernanceDecision,
    GovernanceEngine,
)
from services.governance.models import Principal
from services.governance.policy import Policy
from services.governance.registry import build_standard_governance


def make_registry():
    registry = build_standard_governance()
    registry.register_principal(Principal("ops-001", "Ops One", "operator"))
    registry.register_principal(
        Principal("commander-001", "Commander", "operator")
    )
    return registry


def make_approval_engine():
    return GovernanceApprovalEngine(
        rules=(
            ApprovalRule(
                rule_id="RULE-RESUME-001",
                resource="trading",
                action="resume",
                min_approvers=1,
                required_roles=("INCIDENT_COMMANDER",),
                approval_timeout_seconds=900,
            ),
        )
    )


def make_approval(now):
    return Approval(
        approval_id="APR-001",
        resource="trading",
        action="resume",
        requested_by="ops-001",
        incident_id="INC-001",
        requested_at=now,
        expires_at=now + timedelta(seconds=900),
        policy_id="POLICY-TRADING-RESUME-001",
    )


def resume_context(approval_id="APR-001"):
    return GovernanceContext(
        principal_id="ops-001",
        role_ids=("CONTROL_OPERATOR",),
        resource="trading",
        action="resume",
        environment="production",
        incident_id="INC-001",
        severity="CRITICAL",
        approval_id=approval_id,
        recovery_status="READY",
        reconciliation_status="PASSED",
        risk_status="PASSED",
    )


def test_resume_denied_without_approval():
    registry = make_registry()
    governance = GovernanceEngine(registry=registry)

    decision = governance.evaluate(resume_context(approval_id=None))

    assert decision.effect == DecisionEffect.DENY
    assert decision.reason == "no policy matched"


def test_approval_reevaluation_allows_execution():
    registry = make_registry()
    governance = GovernanceEngine(registry=registry)
    engine = make_approval_engine()
    now = datetime.now(timezone.utc)

    approval = make_approval(now)
    engine.create_request(approval)
    approved = engine.approve(
        approval,
        "commander-001",
        now,
        approver_roles=("INCIDENT_COMMANDER",),
    )
    assert approved.state == ApprovalState.APPROVED

    decision = governance.evaluate(resume_context())
    assert decision.effect == DecisionEffect.ALLOW

    final = engine.authorize_execution(approved, decision, now)
    assert final.effect == DecisionEffect.ALLOW
    assert engine.current_state("APR-001") == ApprovalState.CONSUMED

    event_types = {
        event.event_type for event in engine.auditor.for_approval("APR-001")
    }
    assert ApprovalAuditEventType.APPROVAL_CREATED in event_types
    assert ApprovalAuditEventType.APPROVAL_APPROVED in event_types
    assert ApprovalAuditEventType.APPROVAL_CONSUMED in event_types


def test_consumed_approval_cannot_be_replayed():
    registry = make_registry()
    governance = GovernanceEngine(registry=registry)
    engine = make_approval_engine()
    now = datetime.now(timezone.utc)

    approval = make_approval(now)
    engine.create_request(approval)
    approved = engine.approve(
        approval,
        "commander-001",
        now,
        approver_roles=("INCIDENT_COMMANDER",),
    )
    decision = governance.evaluate(resume_context())

    first = engine.authorize_execution(approved, decision, now)
    assert first.effect == DecisionEffect.ALLOW

    replay = engine.authorize_execution(approved, decision, now)
    assert replay.effect == DecisionEffect.DENY
    assert replay.reason == "approval already consumed"


def test_approved_approval_does_not_bypass_policy_change():
    registry = make_registry()
    governance = GovernanceEngine(registry=registry)
    engine = make_approval_engine()
    now = datetime.now(timezone.utc)

    approval = make_approval(now)
    engine.create_request(approval)
    approved = engine.approve(
        approval,
        "commander-001",
        now,
        approver_roles=("INCIDENT_COMMANDER",),
    )
    assert approved.state == ApprovalState.APPROVED

    # 10:10 —— 政策变了：resume 被冻结。
    registry.register_policy(
        Policy(
            policy_id="POLICY-TRADING-RESUME-BLOCKED-001",
            name="Resume Frozen",
            resource="trading",
            action="resume",
            effect="DENY",
            priority=10,
            conditions=(
                PolicyCondition(
                    field="environment",
                    operator=ConditionOperator.EQUALS,
                    value="production",
                ),
            ),
        )
    )

    decision = governance.evaluate(resume_context())
    assert decision.effect == DecisionEffect.DENY
    assert decision.policy_id == "POLICY-TRADING-RESUME-BLOCKED-001"

    final = engine.authorize_execution(approved, decision, now)
    assert final.effect == DecisionEffect.DENY
    # 10:00 的批准不能绕过 10:10 的 Policy，也不应被消费。
    assert engine.current_state("APR-001") == ApprovalState.APPROVED


def test_approval_binding_blocks_cross_action_use():
    engine = make_approval_engine()
    now = datetime.now(timezone.utc)

    approval = make_approval(now)
    engine.create_request(approval)
    approved = engine.approve(
        approval,
        "commander-001",
        now,
        approver_roles=("INCIDENT_COMMANDER",),
    )

    kill_decision = GovernanceDecision(
        effect=DecisionEffect.ALLOW,
        reason="allowed by POLICY-TRADING-KILL-001",
        policy_id="POLICY-TRADING-KILL-001",
        approval_required=True,
    )

    final = engine.authorize_execution(
        approved,
        kill_decision,
        now,
        action="kill",
    )

    assert final.effect == DecisionEffect.DENY
    assert "binding mismatch" in final.reason
    assert engine.current_state("APR-001") == ApprovalState.APPROVED


def test_consumed_approval_cannot_be_consumed_again():
    now = datetime.now(timezone.utc)
    approval = make_approval(now)
    approved = approve(approval, "commander-001", now)
    consumed = consume(approved)
    assert consumed.state == ApprovalState.CONSUMED

    with pytest.raises(ValueError):
        consume(consumed)


def test_consume_requires_approved_state():
    now = datetime.now(timezone.utc)
    pending = make_approval(now)

    with pytest.raises(ValueError):
        consume(pending)
