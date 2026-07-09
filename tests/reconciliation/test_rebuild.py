from contracts.events.trade_event import TradeEvent
from services.reconciliation.replay_engine import ReplayEngine
from services.reconciliation.snapshot_engine import PositionSnapshot


def test_rebuild_position():
    snapshot = PositionSnapshot(
        symbol="NVDA",
        quantity=100,
    )

    events = [
        TradeEvent(
            event_id="1",
            symbol="NVDA",
            side="BUY",
            quantity=50,
        ),
        TradeEvent(
            event_id="2",
            symbol="NVDA",
            side="SELL",
            quantity=20,
        ),
    ]

    result = ReplayEngine().rebuild(
        snapshot,
        events,
    )

    assert result == 130


def test_rebuild_with_empty_events():
    snapshot = PositionSnapshot(
        symbol="AAPL",
        quantity=50,
    )

    events = []

    result = ReplayEngine().rebuild(
        snapshot,
        events,
    )

    assert result == 50


def test_rebuild_multiple_trades():
    snapshot = PositionSnapshot(
        symbol="MSFT",
        quantity=100,
    )

    events = [
        TradeEvent(event_id="1", symbol="MSFT", side="BUY", quantity=30),
        TradeEvent(event_id="2", symbol="MSFT", side="BUY", quantity=20),
        TradeEvent(event_id="3", symbol="MSFT", side="SELL", quantity=40),
        TradeEvent(event_id="4", symbol="MSFT", side="BUY", quantity=100),
    ]

    result = ReplayEngine().rebuild(
        snapshot,
        events,
    )

    assert result == 210
