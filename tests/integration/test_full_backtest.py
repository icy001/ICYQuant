from datetime import datetime
from pathlib import Path

import pytest

from research.data.csv_provider import CsvMarketDataProvider
from research.data.types import TimeFrame
from research.strategy.moving_average import MovingAverageCrossStrategy
from research.strategy.buy_and_hold import BuyAndHoldStrategy
from research.backtest.runner import BacktestRunner


DATA_DIR = Path(__file__).parent.parent / "research" / "data" / "sample"


class TestFullBacktest:
    def test_full_pipeline_ma_strategy(self):
        data = CsvMarketDataProvider(DATA_DIR)
        
        strategy = MovingAverageCrossStrategy(
            "NVDA",
            short_window=5,
            long_window=10,
        )
        
        runner = BacktestRunner(
            data_provider=data,
            strategy=strategy,
            symbol="NVDA",
            initial_capital=100000.0,
        )
        
        result = runner.run(
            start=datetime(2025, 1, 1),
            end=datetime(2025, 2, 1),
            timeframe=TimeFrame.D1,
        )
        
        assert result.final_equity > 0
        assert result.total_return >= 0
        assert result.max_drawdown >= 0
        assert result.num_trades >= 0

    def test_full_pipeline_buy_and_hold(self):
        data = CsvMarketDataProvider(DATA_DIR)
        
        strategy = BuyAndHoldStrategy("NVDA")
        
        runner = BacktestRunner(
            data_provider=data,
            strategy=strategy,
            symbol="NVDA",
            initial_capital=100000.0,
        )
        
        result = runner.run(
            start=datetime(2025, 1, 1),
            end=datetime(2025, 2, 1),
            timeframe=TimeFrame.D1,
        )
        
        assert result.final_equity > 0
        assert result.num_trades >= 1
        assert "BuyAndHoldStrategy" in result.strategy_name

    def test_performance_report_generation(self):
        data = CsvMarketDataProvider(DATA_DIR)
        
        strategy = MovingAverageCrossStrategy("NVDA")
        
        runner = BacktestRunner(
            data_provider=data,
            strategy=strategy,
            symbol="NVDA",
            initial_capital=100000.0,
        )
        
        result = runner.run(
            start=datetime(2025, 1, 1),
            end=datetime(2025, 2, 1),
            timeframe=TimeFrame.D1,
        )
        
        report_str = str(result)
        
        assert "ICYQuant Performance Report" in report_str
        assert "NVDA" in report_str
        assert "MovingAverageCrossStrategy" in report_str
        assert "Initial Capital" in report_str
        assert "Final Equity" in report_str
        assert "Return" in report_str
        assert "Maximum Drawdown" in report_str
        assert "Trades" in report_str
        assert "Win Rate" in report_str

    def test_trade_journal_records_trades(self):
        data = CsvMarketDataProvider(DATA_DIR)
        
        strategy = BuyAndHoldStrategy("NVDA")
        
        runner = BacktestRunner(
            data_provider=data,
            strategy=strategy,
            symbol="NVDA",
            initial_capital=100000.0,
        )
        
        result = runner.run(
            start=datetime(2025, 1, 1),
            end=datetime(2025, 2, 1),
            timeframe=TimeFrame.D1,
        )
        
        trades = runner.trade_journal.get_all_trades()
        
        assert len(trades) >= 1
        assert trades[0].symbol == "NVDA"
        assert trades[0].strategy == "BuyAndHoldStrategy"