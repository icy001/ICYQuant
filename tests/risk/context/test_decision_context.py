"""
Tests for the risk decision context model.
"""

from dataclasses import FrozenInstanceError
from decimal import Decimal

import pytest

from services.risk.context.decision_context import RiskDecisionContext


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
    )
    base.update(overrides)
    return RiskDecisionContext(**base)


def test_context_holds_decision_inputs():
    context = make_context()

    assert context.account_id == "acc-1"
    assert context.strategy_id == "strat-1"
    assert context.signal_id == "sig-1"
    assert context.instrument_id == "BTCUSDT"
    assert context.side == "BUY"
    assert context.quantity == Decimal("10")
    assert context.price == Decimal("100")


def test_context_holds_snapshot_state():
    context = make_context(
        available_cash=Decimal("1234"),
        current_position=Decimal("55"),
        daily_pnl=Decimal("-42"),
        daily_loss_limit=Decimal("900"),
        max_position=Decimal("150"),
    )

    assert context.available_cash == Decimal("1234")
    assert context.current_position == Decimal("55")
    assert context.daily_pnl == Decimal("-42")
    assert context.daily_loss_limit == Decimal("900")
    assert context.max_position == Decimal("150")


def test_context_identity_defaults_to_none():
    context = make_context()

    assert context.correlation_id is None
    assert context.causation_id is None
    assert context.lineage_id is None


def test_context_is_frozen():
    context = make_context()

    with pytest.raises(FrozenInstanceError):
        context.side = "SELL"
