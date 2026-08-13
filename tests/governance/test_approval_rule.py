"""Tests for services.governance.approval_rule (Commit 28 Part 1.3)."""

from datetime import datetime, timedelta, timezone

import pytest

from services.governance.approval import Approval
from services.governance.approval_rule import ApprovalRule, is_eligible


def make_approval(requested_by="ops-001"):
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


def test_approval_rule_defaults():
    rule = ApprovalRule(
        rule_id="RULE-001",
        resource="trading",
        action="pause",
    )
    assert rule.min_approvers == 1
    assert rule.different_approver_required is True
    assert rule.required_roles == ()
    assert rule.distinct_roles_required is False
    assert rule.approval_timeout_seconds == 900


def test_approval_rule_matches_resource_action():
    rule = ApprovalRule(
        rule_id="RULE-001",
        resource="trading",
        action="pause",
    )
    assert rule.matches("trading", "pause")
    assert not rule.matches("trading", "kill")
    assert not rule.matches("portfolio", "pause")


def test_is_eligible_requires_approver_id():
    rule = ApprovalRule(
        rule_id="RULE-001",
        resource="trading",
        action="resume",
    )
    approval = make_approval()
    assert is_eligible("", ("INCIDENT_COMMANDER",), approval, rule) is False
    assert is_eligible(None, ("INCIDENT_COMMANDER",), approval, rule) is False


def test_is_eligible_self_approval_forbidden():
    rule = ApprovalRule(
        rule_id="RULE-001",
        resource="trading",
        action="resume",
    )
    approval = make_approval(requested_by="ops-001")
    assert is_eligible("ops-001", ("INCIDENT_COMMANDER",), approval, rule) is False


def test_is_eligible_requires_required_role():
    rule = ApprovalRule(
        rule_id="RULE-001",
        resource="trading",
        action="resume",
        required_roles=("INCIDENT_COMMANDER",),
    )
    approval = make_approval()
    assert is_eligible("observer-001", ("OBSERVER",), approval, rule) is False
    assert (
        is_eligible(
            "commander-001",
            ("INCIDENT_COMMANDER",),
            approval,
            rule,
        )
        is True
    )


def test_is_eligible_without_required_roles_accepts_any_other():
    rule = ApprovalRule(
        rule_id="RULE-001",
        resource="trading",
        action="resume",
    )
    approval = make_approval()
    assert is_eligible("observer-001", ("OBSERVER",), approval, rule) is True
    assert is_eligible("commander-001", (), approval, rule) is True


def test_is_eligible_handles_missing_roles():
    rule = ApprovalRule(
        rule_id="RULE-001",
        resource="trading",
        action="resume",
        required_roles=("INCIDENT_COMMANDER",),
    )
    approval = make_approval()
    assert is_eligible("commander-001", None, approval, rule) is False


def test_approval_rule_is_frozen():
    rule = ApprovalRule(
        rule_id="RULE-001",
        resource="trading",
        action="pause",
    )
    with pytest.raises(AttributeError):
        rule.min_approvers = 2  # type: ignore[misc]
