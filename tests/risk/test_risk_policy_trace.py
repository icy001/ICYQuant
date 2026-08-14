"""
Tests for the risk policy evaluation trace (Commit 41 Part 1.3).

The trace answers the audit question "why did the Risk Engine approve or
reject this trade?" by recording every executed policy evaluation in
deterministic order.  First-reject-wins is preserved: policies after the
first rejection are never executed and never appear in the trace.
"""

from dataclasses import FrozenInstanceError
from decimal import Decimal

import pytest

from services.risk.context.decision_context import RiskDecisionContext
from services.risk.decision.risk_decision import (
    RiskDecision,
    RiskDecisionStatus,
)
from services.risk.evaluator.policy_evaluator import RiskPolicyEvaluator
from services.risk.policies.base import RiskPolicy
from services.risk.policies.cash_availability import CashAvailabilityPolicy
from services.risk.policies.daily_loss_limit import DailyLossLimitPolicy
from services.risk.policies.position_limit import PositionLimitPolicy
from services.risk.policy_trace import (
    STATUS_ERROR,
    STATUS_PASS,
    STATUS_REJECT,
    PolicyEvaluationResult,
    RiskPolicyTrace,
)


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


def make_evaluator(policies=None):
    # Spec order: daily_loss (1), position_limit (2), cash (3).
    return RiskPolicyEvaluator(
        policies=policies
        or [
            DailyLossLimitPolicy(),
            PositionLimitPolicy(),
            CashAvailabilityPolicy(),
        ]
    )


class MarketDataPolicy(RiskPolicy):
    policy_id = "market_data"

    def evaluate(self, context: RiskDecisionContext) -> RiskDecision:
        raise RuntimeError("market data unavailable")


def test_all_policies_pass_produces_full_trace():
    evaluator = make_evaluator()

    decision = evaluator.evaluate(make_context())

    assert decision.status == RiskDecisionStatus.APPROVED
    trace = decision.policy_trace
    assert trace is not None
    assert len(trace.evaluations) == 3
    assert [e.status for e in trace.evaluations] == [
        STATUS_PASS,
        STATUS_PASS,
        STATUS_PASS,
    ]


def test_first_reject_wins_and_later_policies_not_traced():
    evaluator = make_evaluator()

    context = make_context(
        quantity=Decimal("2000"),
        price=Decimal("100"),
        available_cash=Decimal("1000000"),
        current_position=Decimal("0"),
        max_position=Decimal("1000"),
    )
    decision = evaluator.evaluate(context)

    assert decision.status == RiskDecisionStatus.REJECTED
    assert decision.rejected_policy == "position_limit"
    trace = decision.policy_trace
    assert trace is not None
    # Cash was never executed: exactly 2 evaluations, never 3.
    assert len(trace.evaluations) == 2
    assert [e.policy_name for e in trace.evaluations] == [
        "daily_loss_limit",
        "position_limit",
    ]
    assert [e.status for e in trace.evaluations] == [
        STATUS_PASS,
        STATUS_REJECT,
    ]


def test_evaluation_order_is_preserved():
    evaluator = make_evaluator()

    decision = evaluator.evaluate(make_context())

    trace = decision.policy_trace
    assert trace is not None
    assert [e.policy_name for e in trace.evaluations] == [
        "daily_loss_limit",
        "position_limit",
        "cash_availability",
    ]
    assert [e.evaluation_order for e in trace.evaluations] == [1, 2, 3]


def test_policy_error_fails_closed_but_trace_keeps_error():
    evaluator = make_evaluator(
        policies=[
            DailyLossLimitPolicy(),
            MarketDataPolicy(),
        ]
    )

    decision = evaluator.evaluate(make_context())

    # ERROR is not REJECT: the rule could not complete its check, so the
    # decision layer fails closed while the trace preserves the real cause.
    assert decision.status == RiskDecisionStatus.REJECTED
    assert decision.policy_id == "market_data"
    trace = decision.policy_trace
    assert trace is not None
    assert len(trace.evaluations) == 2
    assert trace.evaluations[0].status == STATUS_PASS
    assert trace.evaluations[1].status == STATUS_ERROR
    assert trace.evaluations[1].policy_name == "market_data"
    assert trace.evaluations[1].reason == "market data unavailable"


def test_trace_and_results_are_immutable():
    trace = RiskPolicyTrace(
        evaluations=(
            PolicyEvaluationResult(
                policy_name="daily_loss_limit",
                status=STATUS_PASS,
                reason="within limit",
                evaluation_order=1,
            ),
        )
    )

    with pytest.raises(TypeError):
        trace.evaluations[0] = PolicyEvaluationResult(  # type: ignore[index]
            policy_name="daily_loss_limit",
            status=STATUS_REJECT,
            reason=None,
            evaluation_order=1,
        )

    with pytest.raises(FrozenInstanceError):
        trace.evaluations[0].status = STATUS_REJECT  # type: ignore[misc]
