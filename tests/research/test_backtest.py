import pytest
from datetime import datetime, timedelta

from research.backtest.engine import BacktestEngine
from research.backtest.broker import BacktestBroker
from research.backtest.order import Order
from research.backtest.fill import Fill
from research.backtest.context import BacktestContext
from research.backtest.event import Event, BarEvent, SignalEvent, OrderEvent, FillEvent
from research.backtest.queue import EventQueue
from research.portfolio.portfolio import Portfolio
from research.data.bar import Bar
from research.data.provider import MarketDataProvider
from research.data.types import TimeFrame
from research.strategy.base import Strategy
from research.strategy.signal import Signal, SignalType


class MockDataProvider(MarketDataProvider):
    def __init__(self, bars):
        self._bars = bars

    def load_bars(self, symbol, timeframe, start, end):
        return [bar for bar in self._bars if start <= bar.timestamp <= end]


class TestEvent:
    def test_event_creation(self):
        timestamp = datetime(2024, 1, 1)
        event = Event(timestamp=timestamp)
        assert event.timestamp == timestamp

    def test_bar_event_creation(self):
        timestamp = datetime(2024, 1, 1)
        bar = Bar(
            symbol="NVDA",
            timestamp=timestamp,
            open=134.22,
            high=136.50,
            low=133.80,
            close=136.01,
            volume=50234567.0,
        )
        bar_event = BarEvent(timestamp=timestamp, symbol="NVDA", bar=bar)
        assert bar_event.timestamp == timestamp
        assert bar_event.symbol == "NVDA"
        assert bar_event.bar == bar

    def test_signal_event_creation(self):
        timestamp = datetime(2024, 1, 1)
        signal = SignalEvent(
            timestamp=timestamp,
            symbol="NVDA",
            side="BUY",
            quantity=100,
            signal_id="sig_001",
        )
        assert signal.timestamp == timestamp
        assert signal.symbol == "NVDA"
        assert signal.side == "BUY"
        assert signal.quantity == 100

    def test_order_event_creation(self):
        timestamp = datetime(2024, 1, 1)
        order_event = OrderEvent(
            timestamp=timestamp,
            order_id="order_001",
            symbol="NVDA",
            side="BUY",
            quantity=100,
            price=480.0,
        )
        assert order_event.order_id == "order_001"
        assert order_event.symbol == "NVDA"

    def test_fill_event_creation(self):
        timestamp = datetime(2024, 1, 1)
        fill_event = FillEvent(
            timestamp=timestamp,
            fill_id="fill_001",
            order_id="order_001",
            symbol="NVDA",
            side="BUY",
            quantity=100,
            price=480.0,
            cash_change=-48000.0,
        )
        assert fill_event.fill_id == "fill_001"
        assert fill_event.order_id == "order_001"
        assert fill_event.symbol == "NVDA"


class TestEventQueue:
    def test_queue_publish_and_get(self):
        queue = EventQueue()
        event = Event(timestamp=datetime(2024, 1, 1))
        
        queue.publish(event)
        assert not queue.empty()
        assert queue.size() == 1
        
        retrieved = queue.get()
        assert retrieved == event
        assert queue.empty()

    def test_queue_peek(self):
        queue = EventQueue()
        event = Event(timestamp=datetime(2024, 1, 1))
        
        assert queue.peek() is None
        queue.publish(event)
        assert queue.peek() == event
        assert not queue.empty()


class TestOrder:
    def test_order_creation(self):
        order = Order(
            order_id="order_001",
            symbol="NVDA",
            side="BUY",
            quantity=100,
            price=480.0,
            status="SUBMITTED",
        )
        assert order.order_id == "order_001"
        assert order.symbol == "NVDA"
        assert order.side == "BUY"
        assert order.quantity == 100
        assert order.price == 480.0
        assert order.status == "SUBMITTED"


class TestFill:
    def test_fill_creation(self):
        fill = Fill(
            fill_id="fill_001",
            order_id="order_001",
            symbol="NVDA",
            side="BUY",
            quantity=100,
            price=480.0,
            cash_change=-48000.0,
        )
        assert fill.fill_id == "fill_001"
        assert fill.order_id == "order_001"
        assert fill.symbol == "NVDA"
        assert fill.side == "BUY"
        assert fill.quantity == 100
        assert fill.price == 480.0
        assert fill.cash_change == -48000.0


class TestPortfolio:
    def test_portfolio_initialization(self):
        portfolio = Portfolio(initial_cash=100000.0)
        assert portfolio.initial_cash == 100000.0
        assert portfolio.cash == 100000.0
        assert portfolio.holdings.positions == {}

    def test_portfolio_update_fill_buy(self):
        portfolio = Portfolio(initial_cash=100000.0)
        fill = Fill(
            fill_id="fill_001",
            order_id="order_001",
            symbol="NVDA",
            side="BUY",
            quantity=100,
            price=480.0,
            cash_change=-48000.0,
        )
        portfolio.apply_fill(fill)
        assert portfolio.cash == 52000.0
        assert portfolio.holdings.positions["NVDA"].quantity == 100

    def test_portfolio_update_fill_sell(self):
        portfolio = Portfolio(initial_cash=52000.0)
        portfolio.holdings.positions["NVDA"] = portfolio.holdings.get_position("NVDA")
        portfolio.holdings.positions["NVDA"].quantity = 100
        fill = Fill(
            fill_id="fill_002",
            order_id="order_002",
            symbol="NVDA",
            side="SELL",
            quantity=-50,
            price=500.0,
            cash_change=25000.0,
        )
        portfolio.apply_fill(fill)
        assert portfolio.cash == 77000.0
        assert portfolio.holdings.positions["NVDA"].quantity == 50


class TestBacktestContext:
    def test_context_initialization(self):
        context = BacktestContext(
            symbol="NVDA",
            initial_capital=100000.0,
            cash=100000.0,
        )
        assert context.symbol == "NVDA"
        assert context.initial_capital == 100000.0
        assert context.cash == 100000.0
        assert context.positions == {}
        assert context.portfolio is not None

    def test_context_buy(self):
        context = BacktestContext(
            symbol="NVDA",
            initial_capital=100000.0,
            cash=100000.0,
        )
        order = context.buy("NVDA", 100)
        assert order.side == "BUY"
        assert order.quantity == 100
        assert order.order_id in context.orders

    def test_context_sell(self):
        context = BacktestContext(
            symbol="NVDA",
            initial_capital=100000.0,
            cash=100000.0,
        )
        order = context.sell("NVDA", 50)
        assert order.side == "SELL"
        assert order.quantity == 50


class TestBacktestBroker:
    def test_broker_initialization(self):
        context = BacktestContext(symbol="NVDA", initial_capital=100000.0, cash=100000.0)
        broker = BacktestBroker(context)
        
        assert broker.context == context

    def test_submit_order(self):
        context = BacktestContext(symbol="NVDA", initial_capital=100000.0, cash=100000.0)
        broker = BacktestBroker(context)
        
        order = broker.submit_order("NVDA", "BUY", 100, 480.0)
        
        assert order.order_id is not None
        assert order.symbol == "NVDA"
        assert order.side == "BUY"
        assert order.quantity == 100
        assert order.price == 480.0
        assert order.status == "SUBMITTED"

    def test_execute_buy_order(self):
        context = BacktestContext(symbol="NVDA", initial_capital=100000.0, cash=100000.0)
        broker = BacktestBroker(context)
        
        order = broker.submit_order("NVDA", "BUY", 100, 480.0)
        fill = broker.execute_order(order, 480.0)
        
        assert fill is not None
        assert fill.order_id == order.order_id
        assert fill.symbol == "NVDA"
        assert fill.side == "BUY"
        assert fill.quantity == 100
        assert fill.price == 480.0
        assert context.positions["NVDA"] == 100
        assert context.cash < 100000.0

    def test_execute_sell_order(self):
        context = BacktestContext(symbol="NVDA", initial_capital=100000.0, cash=100000.0)
        context.update_position("NVDA", 100)
        broker = BacktestBroker(context)
        
        order = broker.submit_order("NVDA", "SELL", 50, 480.0)
        fill = broker.execute_order(order, 480.0)
        
        assert fill is not None
        assert context.positions["NVDA"] == 50
        assert context.cash > 100000.0


class TestBacktestEngine:
    @pytest.fixture
    def sample_bars(self):
        bars = []
        for i in range(50):
            bars.append(Bar(
                symbol="NVDA",
                timestamp=datetime(2024, 1, 1) + timedelta(days=i),
                open=450 + i,
                high=452 + i,
                low=448 + i,
                close=450 + i,
                volume=1000000 + i * 10000,
            ))
        return bars

    def test_engine_setup(self, sample_bars):
        provider = MockDataProvider(sample_bars)
        
        class TestStrat(Strategy):
            def on_start(self):
                pass
            
            def on_bar(self, bar):
                pass
            
            def on_finish(self):
                pass
        
        engine = BacktestEngine()
        engine.setup(provider, TestStrat(), "NVDA", initial_capital=100000.0)
        
        assert engine.data_provider is not None
        assert engine.strategy is not None
        assert engine.context is not None
        assert engine.broker is not None
        assert engine.tradebook is not None
        assert engine.queue is not None

    def test_engine_run(self, sample_bars):
        provider = MockDataProvider(sample_bars)
        
        class SimpleStrategy(Strategy):
            def on_start(self):
                self.bought = False
            
            def on_bar(self, bar):
                if not self.bought and self.get_context().cash > 48000:
                    self.bought = True
                    return Signal(symbol="NVDA", signal_type=SignalType.BUY, strength=1.0)
                return Signal(symbol="NVDA", signal_type=SignalType.HOLD)
            
            def on_finish(self):
                pass
        
        engine = BacktestEngine()
        engine.setup(provider, SimpleStrategy(), "NVDA", initial_capital=100000.0)
        
        results = engine.run(
            start=datetime(2024, 1, 1),
            end=datetime(2024, 2, 15),
            timeframe=TimeFrame.D1,
        )
        
        assert "total_return" in results
        assert "max_drawdown" in results
        assert "num_trades" in results
        assert "sharpe_ratio" in results
        assert "final_value" in results
        assert "equity_curve" in results

    def test_engine_results(self, sample_bars):
        provider = MockDataProvider(sample_bars)
        
        class BuyAndHold(Strategy):
            def on_start(self):
                self.bought = False
            
            def on_bar(self, bar):
                if not self.bought:
                    self.bought = True
                    return Signal(symbol="NVDA", signal_type=SignalType.BUY, strength=1.0)
                return Signal(symbol="NVDA", signal_type=SignalType.HOLD)
            
            def on_finish(self):
                pass
        
        engine = BacktestEngine()
        engine.setup(provider, BuyAndHold(), "NVDA", initial_capital=100000.0)
        
        results = engine.run(
            start=datetime(2024, 1, 1),
            end=datetime(2024, 2, 15),
            timeframe=TimeFrame.D1,
        )
        
        assert results["initial_capital"] == 100000.0
        assert results["num_trades"] >= 1
        assert "positions" in results
        assert "cash" in results