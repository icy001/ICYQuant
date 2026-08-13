"""Role-based quorum — separation of duties (Commit 28 Part 1.4).

trading:kill 要求 Incident Commander + Risk Operator：
Commander A + Commander B 即使 2/2，distinct_roles 不满足 → REJECTED。
"""

from datetime import datetime, timedelta, timezone

import pytest

from services.governance.approval import ApprovalDecision
from services.governance.quorum import QuorumEvaluator, QuorumRule

NOW = datetime.now(timezone.utc)


def approved_by(approver_id, reason="approve"):
    return ApprovalDecision(
        approval_id="APR-KILL-001",
        approver_id=approver_id,
        approved=True,
        timestamp=NOW,
        reason=reason,
    )


@pytest.fixture
def evaluator():
    return QuorumEvaluator()


def test_two_role_quorum():
    """Spec §31 — Commander + Risk 满足 split quorum。"""
    decisions = [
        approved_by("commander-001"),
        approved_by("risk-001"),
    ]
    roles = {
        "commander-001": ("INCIDENT_COMMANDER",),
        "risk-001": ("RISK_OPERATOR",),
    }
    rule = QuorumRule(
        minimum=2,
        distinct_principals=True,
        required_roles=("INCIDENT_COMMANDER", "RISK_OPERATOR"),
        distinct_roles=True,
    )

    assert QuorumEvaluator().evaluate(decisions, roles, rule)


def test_same_role_does_not_satisfy_split_quorum():
    """Spec §32 — 两个 RISK_OPERATOR 不是 Commander + Risk。"""
    decisions = [
        approved_by("risk-001"),
        approved_by("risk-002"),
    ]
    roles = {
        "risk-001": ("RISK_OPERATOR",),
        "risk-002": ("RISK_OPERATOR",),
    }
    rule = QuorumRule(
        minimum=2,
        required_roles=("INCIDENT_COMMANDER", "RISK_OPERATOR"),
        distinct_roles=True,
    )

    assert not QuorumEvaluator().evaluate(decisions, roles, rule)


def test_two_commanders_do_not_satisfy_distinct_role_quorum():
    # Commander A + Commander B 即使 2/2，distinct_roles=true 也不满足。
    decisions = [
        approved_by("commander-a"),
        approved_by("commander-b"),
    ]
    roles = {
        "commander-a": ("INCIDENT_COMMANDER",),
        "commander-b": ("INCIDENT_COMMANDER",),
    }
    rule = QuorumRule(
        minimum=2,
        required_roles=("INCIDENT_COMMANDER",),
        distinct_roles=True,
    )

    assert not QuorumEvaluator().evaluate(decisions, roles, rule)


def test_required_role_missing_fails(evaluator):
    decisions = [
        approved_by("commander-001"),
        approved_by("risk-001"),
    ]
    roles = {
        "commander-001": ("INCIDENT_COMMANDER",),
        "risk-001": ("RISK_OPERATOR",),
    }
    rule = QuorumRule(
        minimum=2,
        required_roles=("INCIDENT_COMMANDER", "RISK_OPERATOR", "SUPERVISOR"),
    )

    assert not evaluator.evaluate(decisions, roles, rule)


def test_distinct_roles_with_matching_required(evaluator):
    decisions = [
        approved_by("commander-001"),
        approved_by("risk-001"),
    ]
    roles = {
        "commander-001": ("INCIDENT_COMMANDER",),
        "risk-001": ("RISK_OPERATOR",),
    }
    rule = QuorumRule(
        minimum=2,
        required_roles=("INCIDENT_COMMANDER", "RISK_OPERATOR"),
        distinct_roles=True,
    )

    assert evaluator.evaluate(decisions, roles, rule)


def test_approver_roles_default_empty(evaluator):
    # approver_roles 缺失（None）不应崩溃。
    decisions = [approved_by("commander-001")]
    rule = QuorumRule(minimum=1)
    assert evaluator.evaluate(decisions, None, rule)


def test_minimum_met_but_required_role_absent(evaluator):
    decisions = [
        approved_by("commander-001"),
        approved_by("risk-001"),
    ]
    roles = {
        "commander-001": ("INCIDENT_COMMANDER",),
        "risk-001": ("RISK_OPERATOR",),
    }
    rule = QuorumRule(
        minimum=2,
        required_roles=("SUPERVISOR",),
    )

    assert not evaluator.evaluate(decisions, roles, rule)
