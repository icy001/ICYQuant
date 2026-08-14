"""Tests for risk decision aggregation (Commit 37 Part 1.5).

Covers the priority order (REJECT > REVIEW > REDUCE > ALLOW), the accepted
quantity resolution (smallest reduction wins) and the metadata enrichment.
"""

from services.risk.application.decision_aggregator import (
    RiskDecisionAggregator,
)
from services.risk.domain.decision import (
    RiskDecision,
    RiskDecisionStatus,
)


def test_reject_has_highest_priority():
    aggregator = RiskDecisionAggregator()

    result = aggregator.aggregate(
        [
            RiskDecision.allow(quantity=100),
            RiskDecision.reject(
                reason="risk limit",
                rule="risk_limit",
            ),
        ]
    )

    assert result.status == RiskDecisionStatus.REJECT
    assert result.accepted_quantity == 0


def test_reduce_is_stronger_than_allow():
    aggregator = RiskDecisionAggregator()

    result = aggregator.aggregate(
        [
            RiskDecision.allow(quantity=100),
            RiskDecision.reduce(
                quantity=50,
                reason="position limit",
                rule="max_position",
            ),
        ]
    )

    assert result.status == RiskDecisionStatus.REDUCE
    assert result.accepted_quantity == 50


def test_multiple_reductions_use_smallest_quantity():
    aggregator = RiskDecisionAggregator()

    result = aggregator.aggregate(
        [
            RiskDecision.reduce(
                quantity=80,
                reason="position limit",
            ),
            RiskDecision.reduce(
                quantity=40,
                reason="strategy limit",
            ),
        ]
    )

    assert result.status == RiskDecisionStatus.REDUCE
    assert result.accepted_quantity == 40


def test_review_is_stronger_than_reduce():
    aggregator = RiskDecisionAggregator()

    result = aggregator.aggregate(
        [
            RiskDecision.reduce(
                quantity=30,
                reason="position limit",
            ),
            RiskDecision.review(
                reason="unusual order size",
                rule="max_order_size",
            ),
        ]
    )

    assert result.status == RiskDecisionStatus.REVIEW
    assert result.accepted_quantity == 30
    assert result.requires_review


def test_empty_decisions_default_to_allow():
    aggregator = RiskDecisionAggregator()

    result = aggregator.aggregate([])

    assert result.status == RiskDecisionStatus.ALLOW
    assert result.allowed
    assert result.accepted_quantity is None


def test_aggregation_merges_reasons_and_rules():
    aggregator = RiskDecisionAggregator()

    result = aggregator.aggregate(
        [
            RiskDecision.reject(
                reason="daily loss limit",
                rule="daily_loss_limit",
            ),
            RiskDecision.reject(
                reason="position limit",
                rule="max_position",
            ),
        ]
    )

    assert result.status == RiskDecisionStatus.REJECT
    assert set(result.reasons) == {
        "daily loss limit",
        "position limit",
    }
    assert set(result.triggered_rules) == {
        "daily_loss_limit",
        "max_position",
    }
    assert result.metadata["decision_count"] == 2
    assert result.metadata["source_statuses"] == [
        "REJECT",
        "REJECT",
    ]
