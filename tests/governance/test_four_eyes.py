"""Tests for four-eyes control and separation of duties (Commit 28 Part 1.3).

    Operator A --Request--> Approval --Approve--> Operator B

而不是：

    Operator A --Request--> Approval --Approve--> Operator A   (DENY)
"""

from datetime import datetime, timedelta, timezone

import pytest

from services.governance.approval import Approval, ApprovalState, approve
from services.governance.approval_engine import GovernanceApprovalEngine
from services.governance.approval_rule import ApprovalRule


def make_pending_approval(requested_by="ops-001"):
    now = datetime.now(timezone.utc)
    return Approval(
        approval_id="APR-001",
        resource="trading",
        action="resume",
        requested_by=requested_by,
        incident_id="INC-001",
        requested_at=now,
        expires_at=now + timedelta(seconds=900),
    )


def make_engine():
    rule = ApprovalRule(
        rule_id="RULE-RESUME-001",
        resource="trading",
        action="resume",
        min_approvers=1,
        required_roles=("INCIDENT_COMMANDER",),
        approval_timeout_seconds=900,
    )
    return GovernanceApprovalEngine(rules=(rule,))


def test_different_operator_can_approve():
    approval = make_pending_approval(requested_by="ops-001")

    result = approve(
        approval,
        approver_id="commander-001",
        now=datetime.now(timezone.utc),
    )

    assert result.state == ApprovalState.APPROVED
    assert result.approved_by == "commander-001"


def test_requester_cannot_approve_own_request():
    approval = make_pending_approval(requested_by="ops-001")

    with pytest.raises(PermissionError):
        approve(
            approval,
            approver_id="ops-001",
            now=datetime.now(timezone.utc),
        )


def test_engine_four_eyes_pipeline():
    engine = make_engine()
    approval = make_pending_approval(requested_by="ops-001")
    engine.create_request(approval)

    approved = engine.approve(
        approval,
        "commander-001",
        datetime.now(timezone.utc),
        approver_roles=("INCIDENT_COMMANDER",),
    )

    assert approved.state == ApprovalState.APPROVED
    assert approved.approved_by == "commander-001"
    assert approved.requested_by == "ops-001"
    assert approved.requested_by != approved.approved_by


def test_observer_cannot_approve():
    engine = make_engine()
    approval = make_pending_approval(requested_by="ops-001")
    engine.create_request(approval)

    with pytest.raises(PermissionError):
        engine.approve(
            approval,
            "observer-001",
            datetime.now(timezone.utc),
            approver_roles=("OBSERVER",),
        )


def test_engine_self_approval_blocked():
    engine = make_engine()
    approval = make_pending_approval(requested_by="ops-001")
    engine.create_request(approval)

    with pytest.raises(PermissionError):
        engine.approve(
            approval,
            "ops-001",
            datetime.now(timezone.utc),
            approver_roles=("INCIDENT_COMMANDER",),
        )


def test_engine_unknown_rule_raises():
    engine = make_engine()
    now = datetime.now(timezone.utc)
    approval = Approval(
        approval_id="APR-999",
        resource="portfolio",
        action="liquidate",
        requested_by="ops-001",
        requested_at=now,
        expires_at=now + timedelta(seconds=900),
    )

    with pytest.raises(ValueError):
        engine.create_request(approval)
