"""
Tests for the daily loss limit policy.
"""

from decimal import Decimal

from services.risk.context.decision_context import RiskDecisionContext
from services.risk.decision.risk_decision import RiskDecisionStatus
from services.risk.policies.daily_loss_limit import DailyLossLimitPolicy


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


def test_reject_when_daily_loss_limit_exceeded():
    context = make_context(
        daily_pnl=Decimal("-1001"),
        daily_loss_limit=Decimal("1000"),
    )

    decision = DailyLossLimitPolicy().evaluate(context)

    assert decision.status == RiskDecisionStatus.REJECTED
    assert decision.reason_code == "DAILY_LOSS_LIMIT_EXCEEDED"


def test_reject_when_loss_equals_limit():
    context = make_context(
        daily_pnl=Decimal("-1000"),
        daily_loss_limit=Decimal("1000"),
    )

    decision = DailyLossLimitPolicy().evaluate(context)

    assert decision.status == RiskDecisionStatus.REJECTED
    assert decision.reason_code == "DAILY_LOSS_LIMIT_EXCEEDED"


def test_approve_when_within_limit():
    context = make_context(
        daily_pnl=Decimal("-999"),
        daily_loss_limit=Decimal("1000"),
    )

    decision = DailyLossLimitPolicy().evaluate(context)

    assert decision.status == RiskDecisionStatus.APPROVED
    assert decision.policy_id == "daily_loss_limit"


def test_approve_when_profitable():
    context = make_context(
        daily_pnl=Decimal("500"),
        daily_loss_limit=Decimal("1000"),
    )

    decision = DailyLossLimitPolicy().evaluate(context)

    assert decision.status == RiskDecisionStatus.APPROVED


def test_reject_when_limit_not_positive():
    context = make_context(
        daily_loss_limit=Decimal("0"),
    )

    decision = DailyLossLimitPolicy().evaluate(context)

    assert decision.status == RiskDecisionStatus.REJECTED
    assert decision.reason_code == "INVALID_DAILY_LOSS_LIMIT"


def test_decision_propagates_identity_fields():
    context = make_context(
        daily_pnl=Decimal("-2000"),
        daily_loss_limit=Decimal("1000"),
    )

    decision = DailyLossLimitPolicy().evaluate(context)

    assert decision.correlation_id == "corr-1"
    assert decision.causation_id == "event-1"
    assert decision.lineage_id == "lineage-1"
