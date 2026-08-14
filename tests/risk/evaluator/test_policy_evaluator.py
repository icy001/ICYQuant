"""
Tests for the risk policy evaluation pipeline.
"""

from decimal import Decimal

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


def test_pipeline_rejects_on_first_failed_policy():
    evaluator = RiskPolicyEvaluator(
        policies=[
            CashAvailabilityPolicy(),
            PositionLimitPolicy(),
            DailyLossLimitPolicy(),
        ]
    )

    context = make_context(
        side="BUY",
        quantity=Decimal("100"),
        price=Decimal("200"),
        available_cash=Decimal("10000"),
        current_position=Decimal("0"),
        max_position=Decimal("1000"),
    )

    decision = evaluator.evaluate(context)

    assert decision.status == RiskDecisionStatus.REJECTED
    assert decision.reason_code == "INSUFFICIENT_CASH"


def test_pipeline_approves_when_all_policies_pass():
    evaluator = RiskPolicyEvaluator(
        policies=[
            CashAvailabilityPolicy(),
            PositionLimitPolicy(),
            DailyLossLimitPolicy(),
        ]
    )

    context = make_context(
        side="BUY",
        quantity=Decimal("10"),
        price=Decimal("100"),
        available_cash=Decimal("5000"),
        current_position=Decimal("0"),
        max_position=Decimal("1000"),
    )

    decision = evaluator.evaluate(context)

    assert decision.status == RiskDecisionStatus.APPROVED
    assert decision.reason_code == "ALL_POLICIES_PASSED"
    assert decision.policy_id == "risk_pipeline"


def test_pipeline_returns_first_rejection():
    evaluator = RiskPolicyEvaluator(
        policies=[
            PositionLimitPolicy(),
            DailyLossLimitPolicy(),
        ]
    )

    context = make_context(
        side="BUY",
        quantity=Decimal("2000"),
        current_position=Decimal("0"),
        max_position=Decimal("1000"),
        daily_pnl=Decimal("-2000"),
        daily_loss_limit=Decimal("1000"),
    )

    decision = evaluator.evaluate(context)

    assert decision.status == RiskDecisionStatus.REJECTED
    assert decision.reason_code == "POSITION_LIMIT_EXCEEDED"
    assert decision.policy_id == "position_limit"


def test_pipeline_stops_after_first_rejection():
    evaluated = []

    class CountingPolicy(RiskPolicy):

        policy_id = "counting"

        def evaluate(self, context):
            evaluated.append(self.policy_id)
            return RiskDecision(
                status=RiskDecisionStatus.REJECTED,
                reason_code="COUNTED",
                policy_id=self.policy_id,
            )

    class MustNotRunPolicy(RiskPolicy):

        policy_id = "must_not_run"

        def evaluate(self, context):
            raise AssertionError("policy evaluated after first rejection")

    evaluator = RiskPolicyEvaluator(
        policies=[
            CountingPolicy(),
            MustNotRunPolicy(),
        ]
    )

    decision = evaluator.evaluate(make_context())

    assert decision.reason_code == "COUNTED"
    assert evaluated == ["counting"]


def test_pipeline_with_no_policies_approves():
    evaluator = RiskPolicyEvaluator(policies=[])

    decision = evaluator.evaluate(make_context())

    assert decision.status == RiskDecisionStatus.APPROVED
    assert decision.reason_code == "ALL_POLICIES_PASSED"
