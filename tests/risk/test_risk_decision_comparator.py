"""
Tests for the risk decision comparator (Commit 41 Part 1.4).

The comparator is the "why" layer of replay verification: it detects
decision changes, rejecting-policy changes, reason changes and per-policy
trace drift — including policies that were no longer / newly executed.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from services.risk.context_snapshot import RiskDecisionContextSnapshot
from services.risk.decision.decision_record import RiskDecisionRecord
from services.risk.decision.risk_decision import (
    RiskDecision,
    RiskDecisionStatus,
)
from services.risk.decision_comparator import RiskDecisionComparator
from services.risk.policy_trace import (
    PolicyEvaluationResult,
    RiskPolicyTrace,
)

FIXED_NOW = datetime(2026, 8, 14, 12, 0, 0, tzinfo=timezone.utc)

SNAPSHOT = RiskDecisionContextSnapshot(
    account_id="acc-1",
    strategy_id="strat-1",
    signal_id="sig-1",
    instrument="BTCUSDT",
    side="BUY",
    current_position=Decimal("0"),
    proposed_quantity=Decimal("1"),
    available_cash=Decimal("100000"),
    daily_pnl=Decimal("0"),
    daily_loss_limit=Decimal("-1000"),
    position_limit=Decimal("100"),
    market_price=Decimal("50000"),
    snapshot_at=FIXED_NOW,
)


def make_record(
    decision="APPROVED",
    reason="all risk policies passed",
    rejected_policy=None,
    trace=None,
):
    return RiskDecisionRecord(
        decision_id="DEC-001",
        request_id="REQ-001",
        strategy_id="strat-1",
        instrument="BTCUSDT",
        decision=decision,
        reason=reason,
        rejected_policy=rejected_policy,
        policy_trace=trace or RiskPolicyTrace(evaluations=()),
        context_snapshot=SNAPSHOT,
        policy_version="risk-policy-v1",
        created_at=FIXED_NOW,
    )


def make_replayed(
    decision="APPROVED",
    reason="all risk policies passed",
    rejected_policy=None,
    trace=None,
):
    return RiskDecision(
        status=(
            RiskDecisionStatus.APPROVED
            if decision == "APPROVED"
            else RiskDecisionStatus.REJECTED
        ),
        reason=reason,
        policy_id=rejected_policy,
        policy_trace=trace or RiskPolicyTrace(evaluations=()),
    )


def trace(*evaluations):
    return RiskPolicyTrace(evaluations=tuple(evaluations))


def result(name, status, order, reason="reason"):
    return PolicyEvaluationResult(
        policy_name=name,
        status=status,
        reason=reason,
        evaluation_order=order,
    )


def test_identical_decisions_have_no_differences():
    comparator = RiskDecisionComparator()
    original = make_record()
    replayed = make_replayed()

    assert comparator.compare(original, replayed) == ()


def test_decision_change_is_detected():
    comparator = RiskDecisionComparator()
    original = make_record(decision="APPROVED")
    replayed = make_replayed(decision="REJECTED", rejected_policy="position_limit")

    differences = comparator.compare(original, replayed)

    assert "decision changed" in differences


def test_same_decision_different_rejected_policy_is_detected():
    comparator = RiskDecisionComparator()
    original = make_record(
        decision="REJECTED",
        reason="projected position exceeds limit",
        rejected_policy="position_limit",
    )
    replayed = make_replayed(
        decision="REJECTED",
        reason="daily loss limit exceeded",
        rejected_policy="daily_loss_limit",
    )

    differences = comparator.compare(original, replayed)

    assert any("rejected_policy changed" in d for d in differences)
    assert "daily_loss_limit" in " ".join(differences)


def test_reason_change_is_detected():
    comparator = RiskDecisionComparator()
    original = make_record(reason="all risk policies passed")
    replayed = make_replayed(reason="approved after manual review")

    differences = comparator.compare(original, replayed)

    assert any("reason changed" in d for d in differences)


def test_trace_status_change_is_detected():
    comparator = RiskDecisionComparator()
    original = make_record(
        trace=trace(
            result("daily_loss_limit", "PASS", 1),
            result("position_limit", "REJECT", 2),
        )
    )
    replayed = make_replayed(
        trace=trace(
            result("daily_loss_limit", "PASS", 1),
            result("position_limit", "PASS", 2),
            result("cash_availability", "REJECT", 3),
        )
    )

    differences = comparator.compare(original, replayed)

    assert "position_limit changed from REJECT to PASS" in differences
    assert (
        "cash_availability changed from NOT_EXECUTED to REJECT"
        in differences
    )


def test_trace_policy_no_longer_executed_is_detected():
    comparator = RiskDecisionComparator()
    original = make_record(
        trace=trace(
            result("daily_loss_limit", "PASS", 1),
            result("position_limit", "REJECT", 2),
        )
    )
    replayed = make_replayed(
        trace=trace(result("daily_loss_limit", "REJECT", 1))
    )

    differences = comparator.compare(original, replayed)

    assert "position_limit changed from REJECT to NOT_EXECUTED" in differences
    assert "daily_loss_limit changed from PASS to REJECT" in differences


def test_trace_policy_newly_executed_is_detected():
    comparator = RiskDecisionComparator()
    original = make_record(
        trace=trace(result("daily_loss_limit", "REJECT", 1))
    )
    replayed = make_replayed(
        trace=trace(
            result("daily_loss_limit", "PASS", 1),
            result("position_limit", "REJECT", 2),
        )
    )

    differences = comparator.compare(original, replayed)

    assert "position_limit changed from NOT_EXECUTED to REJECT" in differences


def test_identical_rejected_decision_has_no_differences():
    comparator = RiskDecisionComparator()
    original = make_record(
        decision="REJECTED",
        reason="projected position exceeds limit",
        rejected_policy="position_limit",
        trace=trace(
            result("daily_loss_limit", "PASS", 1),
            result("position_limit", "REJECT", 2),
        ),
    )
    replayed = make_replayed(
        decision="REJECTED",
        reason="projected position exceeds limit",
        rejected_policy="position_limit",
        trace=trace(
            result("daily_loss_limit", "PASS", 1),
            result("position_limit", "REJECT", 2),
        ),
    )

    assert comparator.compare(original, replayed) == ()
