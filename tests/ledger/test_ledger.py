import pytest
from datetime import datetime

from services.contracts.dto import TradeDTO
from services.ledger.models.entry import LedgerDirection, LedgerEntry, LedgerType
from services.ledger.service.rebuilder import PositionRebuilder
from services.ledger.service.service import LedgerService
from services.ledger.service.transformer import TradeToLedger


class TestLedgerService:
    def test_record_entry(self):
        service = LedgerService()
        entry = LedgerEntry(
            entry_id="e1",
            user_id="u1",
            event_type="TRADE_FILLED",
            symbol="AAPL",
            ledger_type=LedgerType.POSITION,
            direction=LedgerDirection.CREDIT,
            amount=10.0,
            reference_id="t1",
            timestamp=datetime.utcnow(),
        )
        service.record(entry)
        assert len(service.get_all("u1")) == 1


class TestTradeToLedger:
    def test_convert_trade(self):
        transformer = TradeToLedger()
        trade = TradeDTO(trade_id="t1", user_id="u1", symbol="AAPL", price=100.0, quantity=10.0)
        entries = transformer.convert(trade)
        assert len(entries) == 2


class TestPositionRebuilder:
    def test_rebuild_positions(self):
        rebuilder = PositionRebuilder()
        entries = [
            LedgerEntry(entry_id="e1", user_id="u1", event_type="TRADE_FILLED", symbol="AAPL", ledger_type=LedgerType.POSITION, direction=LedgerDirection.CREDIT, amount=10.0, reference_id="t1", timestamp=datetime.utcnow()),
            LedgerEntry(entry_id="e2", user_id="u1", event_type="TRADE_FILLED", symbol="AAPL", ledger_type=LedgerType.POSITION, direction=LedgerDirection.DEBIT, amount=3.0, reference_id="t2", timestamp=datetime.utcnow()),
        ]
        positions = rebuilder.rebuild(entries)
        assert positions.get("AAPL") == 7.0