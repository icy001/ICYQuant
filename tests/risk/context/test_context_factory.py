"""
Tests for the risk decision context factory.
"""

from decimal import Decimal
from types import SimpleNamespace

from services.risk.context.context_factory import RiskDecisionContextFactory


def make_signal(**overrides):
    data = dict(
        strategy_id="strat-1",
        signal_id="sig-1",
        instrument_id="BTCUSDT",
        side="BUY",
        quantity=Decimal("10"),
        price=Decimal("100"),
        correlation_id="corr-1",
        event_id="event-1",
        lineage_id="lineage-1",
    )
    data.update(overrides)
    return SimpleNamespace(**data)


def make_account_snapshot(**overrides):
    data = dict(
        account_id="acc-1",
        available_cash=Decimal("5000"),
        daily_pnl=Decimal("0"),
        daily_loss_limit=Decimal("1000"),
        max_position=Decimal("100"),
    )
    data.update(overrides)
    return SimpleNamespace(**data)


def make_position_snapshot(**overrides):
    data = dict(quantity=Decimal("25"))
    data.update(overrides)
    return SimpleNamespace(**data)


def test_factory_maps_signal_fields():
    signal = make_signal()
    account = make_account_snapshot()
    position = make_position_snapshot()

    context = RiskDecisionContextFactory().build(signal, account, position)

    assert context.account_id == "acc-1"
    assert context.strategy_id == "strat-1"
    assert context.signal_id == "sig-1"
    assert context.instrument_id == "BTCUSDT"
    assert context.side == "BUY"
    assert context.quantity == Decimal("10")
    assert context.price == Decimal("100")


def test_factory_maps_snapshot_fields():
    signal = make_signal()
    account = make_account_snapshot(
        available_cash=Decimal("4321"),
        daily_pnl=Decimal("-77"),
        daily_loss_limit=Decimal("888"),
        max_position=Decimal("999"),
    )
    position = make_position_snapshot(quantity=Decimal("33"))

    context = RiskDecisionContextFactory().build(signal, account, position)

    assert context.available_cash == Decimal("4321")
    assert context.daily_pnl == Decimal("-77")
    assert context.daily_loss_limit == Decimal("888")
    assert context.max_position == Decimal("999")
    assert context.current_position == Decimal("33")


def test_factory_maps_identity_fields():
    signal = make_signal()
    account = make_account_snapshot()
    position = make_position_snapshot()

    context = RiskDecisionContextFactory().build(signal, account, position)

    assert context.correlation_id == "corr-1"
    assert context.causation_id == "event-1"
    assert context.lineage_id == "lineage-1"


def test_factory_does_not_mutate_sources():
    signal = make_signal()
    account = make_account_snapshot()
    position = make_position_snapshot()

    RiskDecisionContextFactory().build(signal, account, position)

    assert signal.quantity == Decimal("10")
    assert account.available_cash == Decimal("5000")
    assert position.quantity == Decimal("25")
