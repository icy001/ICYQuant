import pytest
from datetime import datetime

from services.contracts.dto import TradeDTO
from services.ledger.event import LedgerEvent
from services.ledger.event_type import LedgerEventType
from services.ledger.repository import EventRepository
from services.ledger.service.rebuilder import CashRebuilder, PositionRebuilder
from services.ledger.service.service import LedgerService
from services.ledger.service.transformer import TradeToLedger
from services.ledger.store import InMemoryEventStore


class TestLedgerService:
    def test_record_deposit(self):
        store = InMemoryEventStore()
        repo = EventRepository(store)
        service = LedgerService(repo)

        event = service.record_deposit("u1", 10000.0)

        assert event.event_type == LedgerEventType.CASH_DEPOSITED
        assert event.payload["amount"] == 10000.0
        events = service.get_events("u1")
        assert len(events) == 1

    def test_record_order_filled(self):
        store = InMemoryEventStore()
        repo = EventRepository(store)
        service = LedgerService(repo)

        event = service.record_order_filled("u1", "o1", "AAPL", "BUY", 100, 150.0)

        assert event.event_type == LedgerEventType.ORDER_FILLED
        assert event.payload["cash_change"] == -15000.0


class TestTradeToLedger:
    def test_convert_trade(self):
        transformer = TradeToLedger()
        trade = TradeDTO(trade_id="t1", user_id="u1", symbol="AAPL", price=100.0, quantity=10.0)
        event = transformer.convert(trade)

        assert isinstance(event, LedgerEvent)
        assert event.event_type == LedgerEventType.ORDER_FILLED
        assert event.payload["symbol"] == "AAPL"
        assert event.payload["quantity"] == 10.0


class TestPositionRebuilder:
    def test_rebuild_positions(self):
        rebuilder = PositionRebuilder()
        events = [
            LedgerEvent(event_type=LedgerEventType.ORDER_FILLED, payload={"symbol": "AAPL", "side": "BUY", "quantity": 10.0}),
            LedgerEvent(event_type=LedgerEventType.ORDER_FILLED, payload={"symbol": "AAPL", "side": "SELL", "quantity": 3.0}),
        ]
        positions = rebuilder.rebuild(events)
        assert positions.get("AAPL") == 7.0


class TestCashRebuilder:
    def test_rebuild_cash(self):
        rebuilder = CashRebuilder()
        events = [
            LedgerEvent(event_type=LedgerEventType.CASH_DEPOSITED, payload={"amount": 100000.0}),
            LedgerEvent(event_type=LedgerEventType.ORDER_FILLED, payload={"cash_change": -10000.0}),
            LedgerEvent(event_type=LedgerEventType.COMMISSION_CHARGED, payload={"amount": 5.0}),
        ]
        cash = rebuilder.rebuild(events)
        assert cash == 89995.0