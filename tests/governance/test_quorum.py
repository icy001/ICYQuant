"""Approval quorum — distinct principals (Commit 28 Part 1.4).

min_approvers = 2 还不够：两个批准可能来自同一个人 / 同一个角色。
QuorumRule 追加 distinct_principals / required_roles / distinct_roles。
"""

from datetime import datetime, timedelta, timezone

import pytest

from services.governance.approval import ApprovalDecision
from services.governance.quorum import QuorumEvaluator, QuorumRule

NOW = datetime.now(timezone.utc)


def approved_by(approver_id, reason="approve"):
    return ApprovalDecision(
        approval_id="APR-001",
        approver_id=approver_id,
        approved=True,
        timestamp=NOW,
        reason=reason,
    )


def rejected_by(approver_id, reason="reject"):
    return ApprovalDecision(
        approval_id="APR-001",
        approver_id=approver_id,
        approved=False,
        timestamp=NOW,
        reason=reason,
    )


@pytest.fixture
def evaluator():
    return QuorumEvaluator()


class TestQuorumRule:

    def test_defaults(self):
        rule = QuorumRule(minimum=2)
        assert rule.distinct_principals is True
        assert rule.required_roles == ()
        assert rule.distinct_roles is False

    def test_custom_values(self):
        rule = QuorumRule(
            minimum=2,
            distinct_principals=True,
            required_roles=("INCIDENT_COMMANDER", "RISK_OPERATOR"),
            distinct_roles=True,
        )
        assert rule.minimum == 2
        assert rule.distinct_principals is True
        assert rule.required_roles == ("INCIDENT_COMMANDER", "RISK_OPERATOR")
        assert rule.distinct_roles is True


class TestQuorumEvaluator:

    def test_below_minimum_fails(self, evaluator):
        rule = QuorumRule(minimum=2)
        assert not evaluator.evaluate([approved_by("commander-001")], {}, rule)

    def test_empty_decisions_fail(self, evaluator):
        assert not evaluator.evaluate([], {}, QuorumRule(minimum=1))

    def test_same_principal_twice_does_not_count_twice(self, evaluator):
        # 重复批准者只算 1 人。
        rule = QuorumRule(minimum=2)
        decisions = [
            approved_by("commander-001"),
            approved_by("commander-001"),
        ]
        assert not evaluator.evaluate(decisions, {}, rule)

    def test_two_distinct_principals_pass(self, evaluator):
        rule = QuorumRule(minimum=2)
        decisions = [
            approved_by("commander-001"),
            approved_by("risk-001"),
        ]
        assert evaluator.evaluate(decisions, {}, rule)

    def test_rejection_does_not_count_as_approval(self, evaluator):
        rule = QuorumRule(minimum=2)
        decisions = [
            approved_by("commander-001"),
            rejected_by("risk-001"),
        ]
        assert not evaluator.evaluate(decisions, {}, rule)

    def test_single_approver_meets_minimum_one(self, evaluator):
        rule = QuorumRule(minimum=1)
        assert evaluator.evaluate([approved_by("commander-001")], {}, rule)

    def test_minimum_zero_and_empty(self, evaluator):
        rule = QuorumRule(minimum=0)
        assert evaluator.evaluate([], {}, rule)
