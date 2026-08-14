"""
Tests for the position limit policy.
"""

from decimal import Decimal

from services.risk.context.decision_context import RiskDecisionContext
from services.risk.decision.risk_decision import RiskDecisionStatus
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


def test_reject_when_position_limit_exceeded():
    context = make_context(
        side="BUY",
        quantity=Decimal("600"),
        current_position=Decimal("500"),
        max_position=Decimal("1000"),
    )

    decision = PositionLimitPolicy().evaluate(context)

    assert decision.status == RiskDecisionStatus.REJECTED
    assert decision.reason_code == "POSITION_LIMIT_EXCEEDED"


def test_approve_when_within_position_limit():
    context = make_context(
        side="BUY",
        quantity=Decimal("100"),
        current_position=Decimal("500"),
        max_position=Decimal("1000"),
    )

    decision = PositionLimitPolicy().evaluate(context)

    assert decision.status == RiskDecisionStatus.APPROVED
    assert decision.policy_id == "position_limit"


def test_reject_invalid_quantity():
    context = make_context(quantity=Decimal("0"))

    decision = PositionLimitPolicy().evaluate(context)

    assert decision.status == RiskDecisionStatus.REJECTED
    assert decision.reason_code == "INVALID_QUANTITY"


def test_reject_negative_quantity():
    context = make_context(quantity=Decimal("-5"))

    decision = PositionLimitPolicy().evaluate(context)

    assert decision.status == RiskDecisionStatus.REJECTED
    assert decision.reason_code == "INVALID_QUANTITY"


def test_reject_invalid_side():
    context = make_context(side="HOLD")

    decision = PositionLimitPolicy().evaluate(context)

    assert decision.status == RiskDecisionStatus.REJECTED
    assert decision.reason_code == "INVALID_SIDE"


def test_sell_reduces_projected_position():
    context = make_context(
        side="SELL",
        quantity=Decimal("600"),
        current_position=Decimal("500"),
        max_position=Decimal("1000"),
    )

    decision = PositionLimitPolicy().evaluate(context)

    assert decision.status == RiskDecisionStatus.APPROVED


def test_reject_short_beyond_max_position():
    context = make_context(
        side="SELL",
        quantity=Decimal("2000"),
        current_position=Decimal("0"),
        max_position=Decimal("1000"),
    )

    decision = PositionLimitPolicy().evaluate(context)

    assert decision.status == RiskDecisionStatus.REJECTED
    assert decision.reason_code == "POSITION_LIMIT_EXCEEDED"
