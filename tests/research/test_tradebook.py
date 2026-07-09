import pytest
from datetime import datetime

from research.tradebook.tradebook import TradeBook, TradeRecord, DailySummary


class TestTradeBook:
    def test_tradebook_initialization(self):
        tradebook = TradeBook()
        
        assert len(tradebook.get_all_trades()) == 0

    def test_record_trade(self):
        tradebook = TradeBook()
        
        trade = tradebook.record_trade(
            symbol="NVDA",
            side="BUY",
            quantity=100,
            price=480.0,
            cash_change=-48000.0,
            timestamp=datetime(2024, 1, 15),
            reason="MA crossover",
            notes="Test trade",
        )
        
        assert trade.trade_id is not None
        assert trade.symbol == "NVDA"
        assert trade.side == "BUY"
        assert trade.quantity == 100
        assert trade.price == 480.0
        assert trade.cash_change == -48000.0
        assert trade.reason == "MA crossover"
        assert trade.notes == "Test trade"

    def test_get_trade(self):
        tradebook = TradeBook()
        
        trade = tradebook.record_trade(
            symbol="NVDA",
            side="BUY",
            quantity=100,
            price=480.0,
            cash_change=-48000.0,
            timestamp=datetime(2024, 1, 15),
        )
        
        retrieved = tradebook.get_trade(trade.trade_id)
        
        assert retrieved is not None
        assert retrieved.trade_id == trade.trade_id
        assert retrieved.symbol == "NVDA"

    def test_get_all_trades(self):
        tradebook = TradeBook()
        
        tradebook.record_trade(
            symbol="NVDA",
            side="BUY",
            quantity=100,
            price=480.0,
            cash_change=-48000.0,
            timestamp=datetime(2024, 1, 15),
        )
        
        tradebook.record_trade(
            symbol="AAPL",
            side="SELL",
            quantity=50,
            price=180.0,
            cash_change=9000.0,
            timestamp=datetime(2024, 1, 16),
        )
        
        trades = tradebook.get_all_trades()
        
        assert len(trades) == 2

    def test_get_trades_by_symbol(self):
        tradebook = TradeBook()
        
        tradebook.record_trade(
            symbol="NVDA",
            side="BUY",
            quantity=100,
            price=480.0,
            cash_change=-48000.0,
            timestamp=datetime(2024, 1, 15),
        )
        
        tradebook.record_trade(
            symbol="AAPL",
            side="SELL",
            quantity=50,
            price=180.0,
            cash_change=9000.0,
            timestamp=datetime(2024, 1, 16),
        )
        
        tradebook.record_trade(
            symbol="NVDA",
            side="SELL",
            quantity=50,
            price=490.0,
            cash_change=24500.0,
            timestamp=datetime(2024, 1, 17),
        )
        
        nvda_trades = tradebook.get_trades_by_symbol("NVDA")
        
        assert len(nvda_trades) == 2

    def test_get_daily_summary(self):
        tradebook = TradeBook()
        
        tradebook.record_trade(
            symbol="NVDA",
            side="BUY",
            quantity=100,
            price=480.0,
            cash_change=-48000.0,
            timestamp=datetime(2024, 1, 15, 10, 30),
        )
        
        tradebook.record_trade(
            symbol="NVDA",
            side="SELL",
            quantity=100,
            price=490.0,
            cash_change=49000.0,
            timestamp=datetime(2024, 1, 15, 14, 0),
        )
        
        tradebook.record_trade(
            symbol="AAPL",
            side="BUY",
            quantity=50,
            price=180.0,
            cash_change=-9000.0,
            timestamp=datetime(2024, 1, 16, 11, 0),
        )
        
        summary = tradebook.get_daily_summary(datetime(2024, 1, 15))
        
        assert summary.total_trades == 2
        assert summary.total_pnl == 1000.0
        assert summary.winning_trades == 1
        assert summary.losing_trades == 1

    def test_get_total_summary(self):
        tradebook = TradeBook()
        
        tradebook.record_trade(
            symbol="NVDA",
            side="BUY",
            quantity=100,
            price=480.0,
            cash_change=-48000.0,
            timestamp=datetime(2024, 1, 15),
        )
        
        tradebook.record_trade(
            symbol="NVDA",
            side="SELL",
            quantity=100,
            price=490.0,
            cash_change=49000.0,
            timestamp=datetime(2024, 1, 16),
        )
        
        summary = tradebook.get_total_summary()
        
        assert summary.total_trades == 2
        assert summary.total_pnl == 1000.0

    def test_generate_trade_report(self):
        tradebook = TradeBook()
        
        tradebook.record_trade(
            symbol="NVDA",
            side="BUY",
            quantity=100,
            price=480.0,
            cash_change=-48000.0,
            timestamp=datetime(2024, 1, 15),
            reason="MA crossover",
        )
        
        report = tradebook.generate_trade_report()
        
        assert "ICYQuant Trade Report" in report
        assert "Total Trades: 1" in report
        assert "NVDA" in report
        assert "BUY" in report
        assert "MA crossover" in report