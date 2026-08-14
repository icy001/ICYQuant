"""
Tests for the cash availability policy.
"""

from decimal import Decimal

from services.risk.context.decision_context import RiskDecisionContext
from services.risk.decision.risk_decision import RiskDecisionStatus
from services.risk.policies.cash_availability import CashAvailabilityPolicy


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


def test_reject_when_cash_is_insufficient():
    context = make_context(
        side="BUY",
        quantity=Decimal("100"),
        price=Decimal("200"),
        available_cash=Decimal("10000"),
    )

    decision = CashAvailabilityPolicy().evaluate(context)

    assert decision.status == RiskDecisionStatus.REJECTED
    assert decision.reason_code == "INSUFFICIENT_CASH"


def test_approve_when_cash_is_sufficient():
    context = make_context(
        side="BUY",
        quantity=Decimal("10"),
        price=Decimal("100"),
        available_cash=Decimal("5000"),
    )

    decision = CashAvailabilityPolicy().evaluate(context)

    assert decision.status == RiskDecisionStatus.APPROVED
    assert decision.policy_id == "cash_availability"


def test_approve_when_cash_equals_required():
    context = make_context(
        side="BUY",
        quantity=Decimal("50"),
        price=Decimal("200"),
        available_cash=Decimal("10000"),
    )

    decision = CashAvailabilityPolicy().evaluate(context)

    assert decision.status == RiskDecisionStatus.APPROVED


def test_approve_sell_without_cash():
    context = make_context(
        side="SELL",
        quantity=Decimal("100"),
        price=Decimal("200"),
        available_cash=Decimal("0"),
    )

    decision = CashAvailabilityPolicy().evaluate(context)

    assert decision.status == RiskDecisionStatus.APPROVED
