import pandas as pd
import pytest
from datetime import datetime
import os

from research.backtest.engine import BacktestEngine
from research.backtest.broker import BacktestBroker, Order, Fill
from research.data.csv_provider import CSVProvider
from research.strategy.base import Strategy
from research.strategy.context import StrategyContext


class TestBacktestBroker:
    def test_broker_initialization(self):
        context = StrategyContext(symbol="NVDA", initial_capital=100000.0)
        broker = BacktestBroker(context)
        
        assert broker.context == context

    def test_submit_order(self):
        context = StrategyContext(symbol="NVDA", initial_capital=100000.0)
        broker = BacktestBroker(context)
        
        order = broker.submit_order("NVDA", "BUY", 100, 480.0)
        
        assert order.order_id is not None
        assert order.symbol == "NVDA"
        assert order.side == "BUY"
        assert order.quantity == 100
        assert order.price == 480.0
        assert order.status == "SUBMITTED"

    def test_execute_buy_order(self):
        context = StrategyContext(symbol="NVDA", initial_capital=100000.0)
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
        context = StrategyContext(symbol="NVDA", initial_capital=100000.0)
        context.update_position("NVDA", 100)
        broker = BacktestBroker(context)
        
        order = broker.submit_order("NVDA", "SELL", 50, 480.0)
        fill = broker.execute_order(order, 480.0)
        
        assert fill is not None
        assert context.positions["NVDA"] == 50
        assert context.cash > 100000.0


class TestBacktestEngine:
    @pytest.fixture
    def test_data_dir(self):
        return "tests/research/data/"

    @pytest.fixture
    def sample_data(self, test_data_dir):
        os.makedirs(test_data_dir, exist_ok=True)
        
        dates = pd.date_range("2024-01-01", periods=50, freq="D")
        data = {
            "datetime": dates,
            "open": 450 + pd.Series(range(50)) * 1,
            "high": 452 + pd.Series(range(50)) * 1,
            "low": 448 + pd.Series(range(50)) * 1,
            "close": 450 + pd.Series(range(50)) * 1,
            "volume": 1000000 + pd.Series(range(50)) * 10000,
        }
        df = pd.DataFrame(data)
        
        csv_path = f"{test_data_dir}NVDA.csv"
        df.to_csv(csv_path, index=False)
        
        yield test_data_dir
        
        if os.path.exists(csv_path):
            os.remove(csv_path)

    def test_engine_setup(self, sample_data):
        provider = CSVProvider(data_dir=sample_data)
        
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

    def test_engine_run(self, sample_data):
        provider = CSVProvider(data_dir=sample_data)
        
        class SimpleStrategy(Strategy):
            def on_start(self):
                self.bought = False
            
            def on_bar(self, bar):
                if not self.bought and self.get_context().cash > 48000:
                    order = self.get_broker().submit_order("NVDA", "BUY", 100)
                    self.bought = True
            
            def on_finish(self):
                pass
        
        engine = BacktestEngine()
        engine.setup(provider, SimpleStrategy(), "NVDA", initial_capital=100000.0)
        
        results = engine.run(
            start=datetime(2024, 1, 1),
            end=datetime(2024, 2, 15)
        )
        
        assert "total_return" in results
        assert "max_drawdown" in results
        assert "num_trades" in results
        assert "sharpe_ratio" in results
        assert "final_value" in results

    def test_engine_results(self, sample_data):
        provider = CSVProvider(data_dir=sample_data)
        
        class BuyAndHold(Strategy):
            def on_start(self):
                self.bought = False
            
            def on_bar(self, bar):
                if not self.bought:
                    order = self.get_broker().submit_order("NVDA", "BUY", 100)
                    self.bought = True
            
            def on_finish(self):
                pass
        
        engine = BacktestEngine()
        engine.setup(provider, BuyAndHold(), "NVDA", initial_capital=100000.0)
        
        results = engine.run(
            start=datetime(2024, 1, 1),
            end=datetime(2024, 2, 15)
        )
        
        assert results["initial_capital"] == 100000.0
        assert results["num_trades"] >= 1
        assert "positions" in results
        assert "cash" in results