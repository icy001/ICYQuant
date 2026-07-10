import pytest

from services.ledger.event import LedgerEvent
from services.ledger.event_type import LedgerEventType
from services.ledger.ledger import Ledger
from services.ledger.cash_projection import CashProjection
from services.ledger.position_projection import PositionProjection


class TestLedgerReplay:

    def test_replay_deposit_and_trade(self):
        cash_projection = CashProjection()
        position_projection = PositionProjection()

        ledger = Ledger()
        ledger.register_projector(cash_projection)
        ledger.register_projector(position_projection)

        deposit_event = LedgerEvent(event_type=LedgerEventType.CASH_DEPOSITED, payload={"amount": 100000.0})
        buy_event = LedgerEvent(event_type=LedgerEventType.ORDER_FILLED, payload={"symbol": "NVDA", "side": "BUY", "price": 100.0, "quantity": 100, "cash_change": -10000.0})
        commission_event = LedgerEvent(event_type=LedgerEventType.COMMISSION_CHARGED, payload={"amount": 5.0})

        ledger.record(deposit_event)
        ledger.record(buy_event)
        ledger.record(commission_event)

        assert cash_projection.cash == 89995.0
        position = position_projection.get_position("NVDA")
        assert position["quantity"] == 100

        cash_projection.reset()
        position_projection.reset()
        assert cash_projection.cash == 0.0
        assert position_projection.state == {}

        ledger.replay()

        assert cash_projection.cash == 89995.0
        position = position_projection.get_position("NVDA")
        assert position["quantity"] == 100
        assert position["avg_cost"] == 100.0

    def test_replay_multiple_trades(self):
        cash_projection = CashProjection()
        position_projection = PositionProjection()

        ledger = Ledger()
        ledger.register_projector(cash_projection)
        ledger.register_projector(position_projection)

        deposit_event = LedgerEvent(event_type=LedgerEventType.CASH_DEPOSITED, payload={"amount": 100000.0})
        buy_event1 = LedgerEvent(event_type=LedgerEventType.ORDER_FILLED, payload={"symbol": "NVDA", "side": "BUY", "price": 100.0, "quantity": 100, "cash_change": -10000.0})
        buy_event2 = LedgerEvent(event_type=LedgerEventType.ORDER_FILLED, payload={"symbol": "NVDA", "side": "BUY", "price": 110.0, "quantity": 50, "cash_change": -5500.0})
        sell_event = LedgerEvent(event_type=LedgerEventType.ORDER_FILLED, payload={"symbol": "NVDA", "side": "SELL", "price": 120.0, "quantity": 150, "cash_change": 18000.0})

        ledger.record(deposit_event)
        ledger.record(buy_event1)
        ledger.record(buy_event2)
        ledger.record(sell_event)

        assert cash_projection.cash == pytest.approx(100000 - 100*100 - 50*110 + 150*120)
        assert "NVDA" not in position_projection.state

    def test_snapshot(self):
        cash_projection = CashProjection()
        position_projection = PositionProjection()

        ledger = Ledger()
        ledger.register_projector(cash_projection)
        ledger.register_projector(position_projection)

        deposit_event = LedgerEvent(event_type=LedgerEventType.CASH_DEPOSITED, payload={"amount": 100000.0})
        buy_event = LedgerEvent(event_type=LedgerEventType.ORDER_FILLED, payload={"symbol": "NVDA", "side": "BUY", "price": 100.0, "quantity": 100, "cash_change": -10000.0})

        ledger.record(deposit_event)
        ledger.record(buy_event)

        snapshot = ledger.snapshot()

        assert "CashProjection" in snapshot
        assert "PositionProjection" in snapshot
        assert snapshot["CashProjection"]["cash"] == 90000.0