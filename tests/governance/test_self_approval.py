"""Tests for self-approval prevention (Commit 28 Part 1.3, Four-Eyes).

核心不变量：Requester != Approver，自己不能批准自己的高风险操作。
"""

from datetime import datetime, timedelta, timezone

import pytest

from services.governance.approval import (
    Approval,
    approve,
    reject,
    validate_approver,
)
from services.governance.approval_rule import ApprovalRule, is_eligible


def make_pending_approval(requested_by="ops-001", expires_seconds=900):
    now = datetime.now(timezone.utc)
    return Approval(
        approval_id="APR-001",
        resource="trading",
        action="resume",
        requested_by=requested_by,
        incident_id="INC-001",
        requested_at=now,
        expires_at=now + timedelta(seconds=expires_seconds),
    )


def test_self_approval_forbidden():
    approval = make_pending_approval(requested_by="ops-001")

    with pytest.raises(PermissionError):
        approve(
            approval,
            approver_id="ops-001",
            now=datetime.now(timezone.utc),
        )


def test_validate_approver_raises_for_requester():
    approval = make_pending_approval(requested_by="ops-001")

    with pytest.raises(PermissionError):
        validate_approver(approval, "ops-001")


def test_validate_approver_passes_for_other_operator():
    approval = make_pending_approval(requested_by="ops-001")
    validate_approver(approval, "commander-001")


def test_self_rejection_forbidden():
    approval = make_pending_approval(requested_by="ops-001")

    with pytest.raises(PermissionError):
        reject(
            approval,
            approver_id="ops-001",
            reason="risk validation failed",
        )


def test_is_eligible_false_for_requester():
    approval = make_pending_approval(requested_by="ops-001")
    rule = ApprovalRule(
        rule_id="RULE-001",
        resource="trading",
        action="resume",
    )

    assert is_eligible("ops-001", ("INCIDENT_COMMANDER",), approval, rule) is False
