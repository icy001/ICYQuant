"""Tests for approval expiration (Commit 28 Part 1.3).

Expired approvals must never execute: "之前已经批准过，所以继续执行" is forbidden.
"""

from datetime import datetime, timedelta, timezone

import pytest

from services.governance.approval import (
    Approval,
    ApprovalState,
    approve,
    expire_approval,
)
from services.governance.approval_engine import GovernanceApprovalEngine
from services.governance.approval_rule import ApprovalRule
from services.governance.audit import ApprovalAuditEventType


def make_expired_approval():
    now = datetime.now(timezone.utc)
    return Approval(
        approval_id="APR-001",
        resource="trading",
        action="resume",
        requested_by="ops-001",
        incident_id="INC-001",
        requested_at=now - timedelta(seconds=901),
        expires_at=now - timedelta(seconds=1),
    )


def test_expired_approval():
    approval = make_expired_approval()
    now = datetime.now(timezone.utc)

    with pytest.raises(ValueError):
        approve(
            approval,
            approver_id="commander-001",
            now=now,
        )


def test_expire_transition_to_terminal():
    approval = make_expired_approval()
    now = datetime.now(timezone.utc)

    expired = expire_approval(approval, now)

    assert expired.state == ApprovalState.EXPIRED


def test_expired_approval_is_terminal():
    approval = make_expired_approval()
    now = datetime.now(timezone.utc)
    expired = expire_approval(approval, now)

    with pytest.raises(ValueError):
        approve(
            expired,
            approver_id="commander-001",
            now=now + timedelta(seconds=1),
        )


def test_pending_not_expired_can_approve():
    now = datetime.now(timezone.utc)
    approval = Approval(
        approval_id="APR-001",
        resource="trading",
        action="resume",
        requested_by="ops-001",
        requested_at=now,
        expires_at=now + timedelta(seconds=900),
    )

    result = approve(approval, approver_id="commander-001", now=now)

    assert result.state == ApprovalState.APPROVED


def test_engine_expire_records_audit():
    engine = GovernanceApprovalEngine(
        rules=(
            ApprovalRule(
                rule_id="RULE-RESUME-001",
                resource="trading",
                action="resume",
                required_roles=("INCIDENT_COMMANDER",),
            ),
        )
    )
    approval = make_expired_approval()
    now = datetime.now(timezone.utc)
    engine.create_request(approval)

    expired = engine.expire(approval, now)

    assert expired.state == ApprovalState.EXPIRED
    assert engine.current_state("APR-001") == ApprovalState.EXPIRED
    event_types = {
        event.event_type for event in engine.auditor.for_approval("APR-001")
    }
    assert ApprovalAuditEventType.APPROVAL_EXPIRED in event_types


def test_expired_approval_cannot_be_authorized():
    engine = GovernanceApprovalEngine(
        rules=(
            ApprovalRule(
                rule_id="RULE-RESUME-001",
                resource="trading",
                action="resume",
                required_roles=("INCIDENT_COMMANDER",),
            ),
        )
    )
    approval = make_expired_approval()
    now = datetime.now(timezone.utc)
    engine.create_request(approval)
    engine.approve(
        approval,
        "commander-001",
        now - timedelta(seconds=5),
        approver_roles=("INCIDENT_COMMANDER",),
    )

    decision = _allow_decision()
    denied = engine.authorize_execution(approval, decision, now)

    assert denied.effect == "DENY"
    assert denied.reason == "approval expired"


def _allow_decision():
    from services.governance.decision import DecisionEffect, GovernanceDecision

    return GovernanceDecision(
        effect=DecisionEffect.ALLOW,
        reason="allowed by POLICY-TRADING-RESUME-001",
        policy_id="POLICY-TRADING-RESUME-001",
        approval_required=True,
    )
