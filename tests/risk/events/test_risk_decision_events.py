"""
Tests for risk decision events and their export from ``RiskDecision``
(Commit 41 Part 1.1).
"""

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from services.risk.context.decision_context import RiskDecisionContext
from services.risk.decision.risk_decision import (
    RiskDecision,
    RiskDecisionStatus,
)
from services.risk.events import (
    RISK_DECISION_APPROVED,
    RISK_DECISION_REJECTED,
    RiskDecisionApproved,
    RiskDecisionRejected,
)
from services.risk.policy_trace import (
    PolicyEvaluationResult,
    RiskPolicyTrace,
)

FIXED_NOW = datetime(2026, 8, 14, 12, 0, 0, tzinfo=timezone.utc)


def make_context(**overrides):
    base = dict(
        account_id="acc-1",
        strategy_id="strat-1",
        signal_id="sig-1",
        instrument_id="BTCUSDT",
        side="BUY",
        quantity=Decimal("10"),
        price=Decimal("100"),
        available_cash=Decimal("5000"),
        current_position=Decimal("0"),
        daily_pnl=Decimal("0"),
        daily_loss_limit=Decimal("1000"),
        max_position=Decimal("100"),
        correlation_id="corr-1",
        causation_id="event-1",
        lineage_id="lineage-1",
    )
    base.update(overrides)
    return RiskDecisionContext(**base)


def test_approved_event_exposes_decision_type():
    event = RiskDecisionApproved(
        decision_id="decision-1",
        account_id="acc-1",
        strategy_id="strat-1",
        signal_id="sig-1",
        instrument_id="BTCUSDT",
        correlation_id="corr-1",
        causation_id="event-1",
        lineage_id="lineage-1",
    )

    assert event.type == RISK_DECISION_APPROVED
    assert event.decision == RISK_DECISION_APPROVED


def test_rejected_event_exposes_decision_type():
    event = RiskDecisionRejected(
        decision_id="decision-1",
        account_id="acc-1",
        strategy_id="strat-1",
        signal_id="sig-1",
        instrument_id="BTCUSDT",
        reason_code="POSITION_LIMIT_EXCEEDED",
        reason="position limit exceeded",
        policy_id="position_limit",
        correlation_id="corr-1",
        causation_id="event-1",
        lineage_id="lineage-1",
    )

    assert event.type == RISK_DECISION_REJECTED
    assert event.decision == RISK_DECISION_REJECTED


def test_approved_decision_exports_approved_event():
    context = make_context()
    decision = RiskDecision(
        status=RiskDecisionStatus.APPROVED,
        reason_code="ALL_POLICIES_PASSED",
        reason="all risk policies passed",
        policy_id="risk_pipeline",
        correlation_id=context.correlation_id,
        causation_id=context.causation_id,
        lineage_id=context.lineage_id,
    )

    event = decision.to_event(
        context,
        decision_id="decision-1",
        request_id="req-1",
        timestamp=FIXED_NOW,
    )

    assert isinstance(event, RiskDecisionApproved)
    assert event.decision_id == "decision-1"
    assert event.request_id == "req-1"
    assert event.strategy_id == "strat-1"
    assert event.instrument_id == "BTCUSDT"
    assert event.decision == RISK_DECISION_APPROVED
    assert event.reason == "all risk policies passed"
    assert event.timestamp == FIXED_NOW
    assert event.correlation_id == "corr-1"
    assert event.causation_id == "event-1"
    assert event.lineage_id == "lineage-1"
    # Commit 41 Part 1.3: absent trace exports as None.
    assert event.policy_trace is None


def test_event_carries_policy_trace_when_present():
    context = make_context()
    trace = RiskPolicyTrace(
        evaluations=(
            PolicyEvaluationResult(
                policy_name="daily_loss_limit",
                status="PASS",
                reason="within limit",
                evaluation_order=1,
            ),
            PolicyEvaluationResult(
                policy_name="position_limit",
                status="REJECT",
                reason="projected position exceeds limit",
                evaluation_order=2,
            ),
        )
    )
    decision = RiskDecision(
        status=RiskDecisionStatus.REJECTED,
        reason_code="POSITION_LIMIT_EXCEEDED",
        reason="projected position exceeds limit",
        policy_id="position_limit",
        correlation_id=context.correlation_id,
        causation_id=context.causation_id,
        lineage_id=context.lineage_id,
        policy_trace=trace,
    )

    event = decision.to_event(
        context,
        decision_id="decision-1",
        request_id="req-1",
        timestamp=FIXED_NOW,
    )

    assert isinstance(event, RiskDecisionRejected)
    assert event.policy_trace == trace


def test_rejected_decision_exports_rejected_event():
    context = make_context()
    decision = RiskDecision(
        status=RiskDecisionStatus.REJECTED,
        reason_code="POSITION_LIMIT_EXCEEDED",
        reason="position limit exceeded",
        policy_id="position_limit",
        correlation_id=context.correlation_id,
        causation_id=context.causation_id,
        lineage_id=context.lineage_id,
    )

    event = decision.to_event(
        context,
        decision_id="decision-2",
        request_id="req-2",
        timestamp=FIXED_NOW,
    )

    assert isinstance(event, RiskDecisionRejected)
    assert event.decision_id == "decision-2"
    assert event.request_id == "req-2"
    assert event.decision == RISK_DECISION_REJECTED
    assert event.policy_id == "position_limit"
    assert event.reason_code == "POSITION_LIMIT_EXCEEDED"
    assert event.reason == "position limit exceeded"
    assert event.timestamp == FIXED_NOW


def test_rejected_policy_exposes_rejecting_policy():
    context = make_context()
    approved = RiskDecision(
        status=RiskDecisionStatus.APPROVED,
        reason_code="ALL_POLICIES_PASSED",
        policy_id="risk_pipeline",
        correlation_id=context.correlation_id,
        causation_id=context.causation_id,
        lineage_id=context.lineage_id,
    )
    rejected = RiskDecision(
        status=RiskDecisionStatus.REJECTED,
        reason_code="POSITION_LIMIT_EXCEEDED",
        policy_id="position_limit",
        correlation_id=context.correlation_id,
        causation_id=context.causation_id,
        lineage_id=context.lineage_id,
    )

    assert approved.rejected_policy is None
    assert rejected.rejected_policy == "position_limit"


def test_decision_events_are_frozen():
    event = RiskDecisionApproved(
        decision_id="decision-1",
        account_id="acc-1",
        strategy_id="strat-1",
        signal_id="sig-1",
        instrument_id="BTCUSDT",
        correlation_id="corr-1",
        causation_id="event-1",
        lineage_id="lineage-1",
    )

    with pytest.raises(Exception):
        event.decision_id = "mutated"  # type: ignore[misc]
