"""Tests for approval rejection (Commit 28 Part 1.3).

Rejection 必须有 reason：Audit 必须能回答"为什么没有批准？"。
"""

from datetime import datetime, timedelta, timezone

import pytest

from services.governance.approval import (
    Approval,
    ApprovalState,
    approve,
    reject,
)
from services.governance.approval_engine import GovernanceApprovalEngine
from services.governance.approval_rule import ApprovalRule
from services.governance.audit import ApprovalAuditEventType


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
    return GovernanceApprovalEngine(
        rules=(
            ApprovalRule(
                rule_id="RULE-RESUME-001",
                resource="trading",
                action="resume",
                required_roles=("INCIDENT_COMMANDER",),
            ),
        )
    )


def test_reject_requires_reason():
    approval = make_pending_approval()

    with pytest.raises(ValueError):
        reject(
            approval,
            approver_id="commander-001",
            reason="",
        )


def test_reject_self_forbidden():
    approval = make_pending_approval(requested_by="ops-001")

    with pytest.raises(PermissionError):
        reject(
            approval,
            approver_id="ops-001",
            reason="risk validation failed",
        )


def test_reject_transition():
    approval = make_pending_approval()

    rejected = reject(
        approval,
        approver_id="commander-001",
        reason="Recovery validation failed",
    )

    assert rejected.state == ApprovalState.REJECTED
    assert rejected.rejection_reason == "Recovery validation failed"


def test_rejected_approval_is_terminal():
    approval = make_pending_approval()
    rejected = reject(
        approval,
        approver_id="commander-001",
        reason="risk validation failed",
    )

    with pytest.raises(ValueError):
        approve(
            rejected,
            approver_id="commander-001",
            now=datetime.now(timezone.utc),
        )


def test_engine_reject_records_audit():
    engine = make_engine()
    approval = make_pending_approval()
    engine.create_request(approval)

    rejected = engine.reject(
        approval,
        "commander-001",
        "risk validation failed",
        approver_roles=("INCIDENT_COMMANDER",),
    )

    assert rejected.state == ApprovalState.REJECTED
    assert engine.current_state("APR-001") == ApprovalState.REJECTED
    event_types = {
        event.event_type for event in engine.auditor.for_approval("APR-001")
    }
    assert ApprovalAuditEventType.APPROVAL_REJECTED in event_types


def test_engine_reject_requires_reason():
    engine = make_engine()
    approval = make_pending_approval()
    engine.create_request(approval)

    with pytest.raises(ValueError):
        engine.reject(
            approval,
            "commander-001",
            "",
            approver_roles=("INCIDENT_COMMANDER",),
        )
