import pytest

from research.portfolio.position import Position
from research.portfolio.holdings import Holdings
from research.portfolio.portfolio import Portfolio


class TestPosition:
    def test_position_initialization(self):
        pos = Position("NVDA")
        assert pos.symbol == "NVDA"
        assert pos.quantity == 0
        assert pos.average_price == 0

    def test_position_increase(self):
        pos = Position("NVDA")
        pos.increase(100, 150.0)
        assert pos.quantity == 100
        assert pos.average_price == 150.0

    def test_position_increase_multiple(self):
        pos = Position("NVDA")
        pos.increase(100, 150.0)
        pos.increase(50, 160.0)
        assert pos.quantity == 150
        assert pos.average_price == (100 * 150 + 50 * 160) / 150

    def test_position_decrease(self):
        pos = Position("NVDA", quantity=100, average_price=150.0)
        pos.decrease(50, 155.0)
        assert pos.quantity == 50


class TestHoldings:
    def test_holdings_initialization(self):
        holdings = Holdings()
        assert holdings.positions == {}

    def test_get_position_new(self):
        holdings = Holdings()
        pos = holdings.get_position("NVDA")
        assert pos.symbol == "NVDA"
        assert pos.quantity == 0

    def test_get_position_existing(self):
        holdings = Holdings()
        holdings.get_position("NVDA").quantity = 100
        pos = holdings.get_position("NVDA")
        assert pos.quantity == 100

    def test_multiple_positions(self):
        holdings = Holdings()
        holdings.get_position("NVDA").quantity = 100
        holdings.get_position("GLD").quantity = 50
        assert len(holdings.positions) == 2
        assert holdings.positions["NVDA"].quantity == 100
        assert holdings.positions["GLD"].quantity == 50


class TestPortfolio:
    def test_portfolio_initialization(self):
        portfolio = Portfolio(100000)
        assert portfolio.cash == 100000
        assert portfolio.holdings.positions == {}

    def test_multi_asset_position(self):
        portfolio = Portfolio(100000)
        
        class Fill:
            def __init__(self, symbol, quantity, price):
                self.symbol = symbol
                self.quantity = quantity
                self.price = price
        
        portfolio.apply_fill(Fill("NVDA", 100, 150))
        portfolio.apply_fill(Fill("GLD", 50, 200))
        
        assert portfolio.holdings.positions["NVDA"].quantity == 100
        assert portfolio.holdings.positions["GLD"].quantity == 50

    def test_portfolio_apply_fill_buy(self):
        portfolio = Portfolio(100000)
        
        class Fill:
            def __init__(self, symbol, quantity, price):
                self.symbol = symbol
                self.quantity = quantity
                self.price = price
        
        portfolio.apply_fill(Fill("NVDA", 100, 150))
        
        assert portfolio.cash == 85000
        assert portfolio.holdings.positions["NVDA"].quantity == 100

    def test_portfolio_apply_fill_sell(self):
        portfolio = Portfolio(85000)
        
        class Fill:
            def __init__(self, symbol, quantity, price):
                self.symbol = symbol
                self.quantity = quantity
                self.price = price
        
        portfolio.holdings.get_position("NVDA").quantity = 100
        portfolio.apply_fill(Fill("NVDA", -50, 160))
        
        assert portfolio.cash == 93000
        assert portfolio.holdings.positions["NVDA"].quantity == 50

    def test_market_value(self):
        portfolio = Portfolio(100000)
        
        class Fill:
            def __init__(self, symbol, quantity, price):
                self.symbol = symbol
                self.quantity = quantity
                self.price = price
        
        portfolio.apply_fill(Fill("NVDA", 100, 150))
        portfolio.apply_fill(Fill("GLD", 50, 200))
        
        market_value = portfolio.market_value({"NVDA": 155, "GLD": 210})
        assert market_value == 100 * 155 + 50 * 210

    def test_equity(self):
        portfolio = Portfolio(100000)
        
        class Fill:
            def __init__(self, symbol, quantity, price):
                self.symbol = symbol
                self.quantity = quantity
                self.price = price
        
        portfolio.apply_fill(Fill("NVDA", 100, 150))
        
        equity = portfolio.equity({"NVDA": 160})
        assert equity == 85000 + 100 * 160