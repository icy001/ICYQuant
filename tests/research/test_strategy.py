import pytest

from research.strategy.base import Strategy
from research.strategy.context import StrategyContext


class TestStrategyContext:
    def test_context_initialization(self):
        context = StrategyContext(symbol="NVDA", initial_capital=50000.0)
        
        assert context.symbol == "NVDA"
        assert context.initial_capital == 50000.0
        assert context.cash == 50000.0
        assert context.positions == {}

    def test_update_position(self):
        context = StrategyContext(symbol="NVDA")
        
        context.update_position("NVDA", 100)
        assert context.positions["NVDA"] == 100
        
        context.update_position("NVDA", 50)
        assert context.positions["NVDA"] == 150
        
        context.update_position("AAPL", 200)
        assert context.positions["AAPL"] == 200

    def test_get_position(self):
        context = StrategyContext(symbol="NVDA")
        
        assert context.get_position("NVDA") == 0.0
        
        context.update_position("NVDA", 100)
        assert context.get_position("NVDA") == 100.0
        
        assert context.get_position("AAPL") == 0.0

    def test_update_cash(self):
        context = StrategyContext(symbol="NVDA", initial_capital=100000.0)
        
        context.update_cash(-50000)
        assert context.cash == 50000.0
        
        context.update_cash(25000)
        assert context.cash == 75000.0


class TestStrategyBase:
    def test_strategy_initialization(self):
        class TestStrat(Strategy):
            def on_start(self):
                pass
            
            def on_bar(self, bar):
                pass
            
            def on_finish(self):
                pass
        
        strat = TestStrat()
        assert not strat.is_initialized()

    def test_strategy_initialize(self):
        class TestStrat(Strategy):
            def on_start(self):
                pass
            
            def on_bar(self, bar):
                pass
            
            def on_finish(self):
                pass
        
        strat = TestStrat()
        context = StrategyContext(symbol="NVDA")
        broker = None
        data_provider = None
        
        strat.initialize(context, broker, data_provider)
        
        assert strat.is_initialized()
        assert strat.get_context() == context
        assert strat.get_broker() == broker
        assert strat.get_data_provider() == data_provider