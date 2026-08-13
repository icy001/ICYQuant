"""Tests for ApprovalAggregator multi-approval logic (Commit 28 Part 1.3).

- 任何拒绝 => REJECTED
- 重复 Approver 只算 1 人（duplicate approval 不能凑人数）
- 达到 min_approvers 个不同 Approver => APPROVED，否则 PENDING
- distinct_roles_required 时还要求不同角色
"""

from datetime import datetime, timedelta, timezone

from services.governance.approval import (
    ApprovalAggregator,
    ApprovalDecision,
    ApprovalState,
)
from services.governance.approval_rule import ApprovalRule


def make_decision(
    approval_id="APR-001",
    approver_id="commander-001",
    approved=True,
    reason=None,
    approver_roles=(),
):
    now = datetime.now(timezone.utc)
    return ApprovalDecision(
        approval_id=approval_id,
        approver_id=approver_id,
        approved=approved,
        timestamp=now,
        reason=reason,
        approver_roles=approver_roles,
    )


def make_rule(min_approvers=1, distinct_roles_required=False):
    return ApprovalRule(
        rule_id="RULE-001",
        resource="trading",
        action="kill",
        min_approvers=min_approvers,
        distinct_roles_required=distinct_roles_required,
    )


def test_duplicate_approver_does_not_count_twice():
    decisions = [
        make_decision(approver_id="commander-001"),
        make_decision(approver_id="commander-001"),
    ]
    rule = make_rule(min_approvers=2)

    state = ApprovalAggregator().evaluate(decisions, rule)

    assert state == ApprovalState.PENDING


def test_two_approvers():
    decisions = [
        make_decision(approver_id="commander-001"),
        make_decision(approver_id="risk-001"),
    ]
    rule = make_rule(min_approvers=2)

    state = ApprovalAggregator().evaluate(decisions, rule)

    assert state == ApprovalState.APPROVED


def test_one_approver_below_min_approvers():
    decisions = [make_decision(approver_id="commander-001")]
    rule = make_rule(min_approvers=2)

    state = ApprovalAggregator().evaluate(decisions, rule)

    assert state == ApprovalState.PENDING


def test_rejection_blocks_request():
    decisions = [
        make_decision(
            approver_id="commander-001",
            approved=False,
            reason="risk validation failed",
        ),
    ]
    rule = make_rule(min_approvers=1)

    state = ApprovalAggregator().evaluate(decisions, rule)

    assert state == ApprovalState.REJECTED


def test_any_rejection_rejects_even_with_enough_approvers():
    decisions = [
        make_decision(approver_id="commander-001", approved=True),
        make_decision(approver_id="risk-001", approved=True),
        make_decision(approver_id="compliance-001", approved=False, reason="hold"),
    ]
    rule = make_rule(min_approvers=2)

    state = ApprovalAggregator().evaluate(decisions, rule)

    assert state == ApprovalState.REJECTED


def test_distinct_roles_required_blocks_same_role():
    decisions = [
        make_decision(
            approver_id="commander-001",
            approver_roles=("INCIDENT_COMMANDER",),
        ),
        make_decision(
            approver_id="commander-002",
            approver_roles=("INCIDENT_COMMANDER",),
        ),
    ]
    rule = make_rule(min_approvers=2, distinct_roles_required=True)

    state = ApprovalAggregator().evaluate(decisions, rule)

    assert state == ApprovalState.PENDING


def test_distinct_roles_required_allows_role_diversity():
    decisions = [
        make_decision(
            approver_id="commander-001",
            approver_roles=("INCIDENT_COMMANDER",),
        ),
        make_decision(
            approver_id="risk-001",
            approver_roles=("RISK_OPERATOR",),
        ),
    ]
    rule = make_rule(min_approvers=2, distinct_roles_required=True)

    state = ApprovalAggregator().evaluate(decisions, rule)

    assert state == ApprovalState.APPROVED
