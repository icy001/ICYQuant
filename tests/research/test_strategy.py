import pytest
from datetime import datetime

from research.strategy.base import Strategy
from research.strategy.context import StrategyContext
from research.strategy.signal import Signal, SignalType
from research.strategy.buy_and_hold import BuyAndHoldStrategy
from research.strategy.moving_average import MovingAverageCrossStrategy
from research.data.bar import Bar


class TestSignal:
    def test_signal_creation(self):
        signal = Signal(
            symbol="NVDA",
            signal_type=SignalType.BUY,
            strength=1.0,
        )
        assert signal.symbol == "NVDA"
        assert signal.signal_type == SignalType.BUY
        assert signal.strength == 1.0

    def test_signal_hold(self):
        signal = Signal(
            symbol="NVDA",
            signal_type=SignalType.HOLD,
        )
        assert signal.signal_type == SignalType.HOLD
        assert signal.strength == 0.0

    def test_signal_sell(self):
        signal = Signal(
            symbol="NVDA",
            signal_type=SignalType.SELL,
            strength=0.8,
        )
        assert signal.signal_type == SignalType.SELL
        assert signal.strength == 0.8


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
            def on_bar(self, bar):
                return Signal(symbol="NVDA", signal_type=SignalType.HOLD)
        
        strat = TestStrat()
        assert not strat.is_initialized()

    def test_strategy_initialize(self):
        class TestStrat(Strategy):
            def on_bar(self, bar):
                return Signal(symbol="NVDA", signal_type=SignalType.HOLD)
        
        strat = TestStrat()
        context = StrategyContext(symbol="NVDA")
        broker = None
        data_provider = None
        
        strat.initialize(context, broker, data_provider)
        
        assert strat.is_initialized()
        assert strat.get_context() == context
        assert strat.get_broker() == broker
        assert strat.get_data_provider() == data_provider


class TestBuyAndHoldStrategy:
    def test_buy_and_hold_first_bar(self):
        strategy = BuyAndHoldStrategy("NVDA")
        
        bar = Bar(
            symbol="NVDA",
            timestamp=datetime(2024, 1, 1),
            open=134.22,
            high=136.50,
            low=133.80,
            close=136.01,
            volume=50234567.0,
        )
        
        signal = strategy.on_bar(bar)
        
        assert signal.symbol == "NVDA"
        assert signal.signal_type == SignalType.BUY
        assert signal.strength == 1.0

    def test_buy_and_hold_subsequent_bars(self):
        strategy = BuyAndHoldStrategy("NVDA")
        
        bar1 = Bar(
            symbol="NVDA",
            timestamp=datetime(2024, 1, 1),
            open=134.22,
            high=136.50,
            low=133.80,
            close=136.01,
            volume=50234567.0,
        )
        
        bar2 = Bar(
            symbol="NVDA",
            timestamp=datetime(2024, 1, 2),
            open=136.01,
            high=137.10,
            low=135.40,
            close=136.80,
            volume=41234567.0,
        )
        
        signal1 = strategy.on_bar(bar1)
        signal2 = strategy.on_bar(bar2)
        
        assert signal1.signal_type == SignalType.BUY
        assert signal2.signal_type == SignalType.HOLD


class TestMovingAverageCrossStrategy:
    def test_moving_average_warm_up(self):
        strategy = MovingAverageCrossStrategy("NVDA", short_window=3, long_window=5)
        
        for i in range(4):
            bar = Bar(
                symbol="NVDA",
                timestamp=datetime(2024, 1, 1 + i),
                open=100 + i,
                high=102 + i,
                low=98 + i,
                close=100 + i,
                volume=1000000.0,
            )
            signal = strategy.on_bar(bar)
            assert signal.signal_type == SignalType.HOLD

    def test_moving_average_buy_signal(self):
        strategy = MovingAverageCrossStrategy("NVDA", short_window=3, long_window=5)
        
        for i in range(5):
            bar = Bar(
                symbol="NVDA",
                timestamp=datetime(2024, 1, 1 + i),
                open=100 + i,
                high=102 + i,
                low=98 + i,
                close=100 + i,
                volume=1000000.0,
            )
            strategy.on_bar(bar)
        
        bar = Bar(
            symbol="NVDA",
            timestamp=datetime(2024, 1, 6),
            open=110,
            high=112,
            low=108,
            close=110,
            volume=1000000.0,
        )
        signal = strategy.on_bar(bar)
        
        assert signal.signal_type == SignalType.BUY

    def test_moving_average_sell_signal(self):
        strategy = MovingAverageCrossStrategy("NVDA", short_window=3, long_window=5)
        
        for i in range(5):
            bar = Bar(
                symbol="NVDA",
                timestamp=datetime(2024, 1, 1 + i),
                open=100,
                high=102,
                low=98,
                close=100,
                volume=1000000.0,
            )
            strategy.on_bar(bar)
        
        signal = strategy.on_bar(bar)
        
        assert signal.signal_type == SignalType.SELL