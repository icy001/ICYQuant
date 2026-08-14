"""Tests for the risk decision domain model (Commit 37 Part 1.5).

Covers the four gate outcomes (ALLOW / REJECT / REDUCE / REVIEW), the
convenience factory methods and the boolean convenience properties.
"""

from services.risk.domain.decision import (
    RiskDecision,
    RiskDecisionStatus,
)


def test_allow_decision():
    decision = RiskDecision.allow(quantity=100)

    assert decision.status == RiskDecisionStatus.ALLOW
    assert decision.allowed
    assert decision.accepted_quantity == 100


def test_reject_decision():
    decision = RiskDecision.reject(
        reason="daily loss limit exceeded",
        rule="daily_loss_limit",
    )

    assert decision.rejected
    assert decision.accepted_quantity is None
    assert "daily loss limit exceeded" in decision.reasons
    assert "daily_loss_limit" in decision.triggered_rules


def test_reduce_decision():
    decision = RiskDecision.reduce(
        quantity=50,
        reason="position limit",
        rule="max_position",
    )

    assert decision.reduced
    assert decision.accepted_quantity == 50
    assert "position limit" in decision.reasons
    assert "max_position" in decision.triggered_rules


def test_review_decision():
    decision = RiskDecision.review(
        reason="unusual order size",
        rule="max_order_size",
    )

    assert decision.status == RiskDecisionStatus.REVIEW
    assert decision.requires_review
    assert not decision.allowed
    assert decision.accepted_quantity is None
    assert "unusual order size" in decision.reasons
    assert "max_order_size" in decision.triggered_rules


def test_decision_metadata():
    decision = RiskDecision.reject(
        reason="risk limit",
        metadata={"source": "pre-trade"},
    )

    assert decision.metadata == {"source": "pre-trade"}


def test_status_is_enum_string():
    assert RiskDecisionStatus.ALLOW.value == "ALLOW"
    assert RiskDecisionStatus.REJECT.value == "REJECT"
    assert RiskDecisionStatus.REDUCE.value == "REDUCE"
    assert RiskDecisionStatus.REVIEW.value == "REVIEW"
