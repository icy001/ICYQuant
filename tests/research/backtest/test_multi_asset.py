import pytest
from datetime import datetime, timedelta

from research.backtest.timeline import Timeline
from research.backtest.multi_asset_engine import MultiAssetBacktestEngine
from research.data.bar import Bar
from research.data.provider import MarketDataProvider
from research.strategy.base import Strategy
from research.strategy.signal import Signal, SignalType


class MockDataProvider(MarketDataProvider):
    def __init__(self, data):
        self._data = data
    
    def load_bars(self, symbol, timeframe, start, end):
        return self._data.get(symbol, [])


class TestTimeline:
    def test_timeline_merge(self):
        timeline = Timeline()
        
        bars_nvda = [
            Bar("NVDA", datetime(2025, 1, 2), 134, 136, 133, 136, 1000000),
            Bar("NVDA", datetime(2025, 1, 3), 136, 137, 135, 137, 1000000),
        ]
        
        bars_gld = [
            Bar("GLD", datetime(2025, 1, 2), 198, 200, 197, 199, 500000),
            Bar("GLD", datetime(2025, 1, 4), 199, 201, 198, 200, 500000),
        ]
        
        timeline.merge({"NVDA": bars_nvda, "GLD": bars_gld})
        
        timestamps = [t for t, _ in timeline]
        assert len(timestamps) == 3
        assert datetime(2025, 1, 2) in timestamps
        assert datetime(2025, 1, 3) in timestamps
        assert datetime(2025, 1, 4) in timestamps

    def test_timeline_get_snapshot(self):
        timeline = Timeline()
        
        bars_nvda = [
            Bar("NVDA", datetime(2025, 1, 2), 134, 136, 133, 136, 1000000),
        ]
        
        timeline.merge({"NVDA": bars_nvda})
        
        snapshot = timeline.get_snapshot(datetime(2025, 1, 2))
        assert "NVDA" in snapshot


class TestMultiAssetEngine:
    def test_multi_asset_engine_setup(self):
        data = MockDataProvider({})
        
        class SimpleStrategy(Strategy):
            def on_bar(self, bar):
                return Signal(symbol=bar.symbol, signal_type=SignalType.HOLD)
        
        engine = MultiAssetBacktestEngine(
            data_provider=data,
            strategy=SimpleStrategy(),
            symbols=["NVDA", "GLD"],
            initial_capital=100000.0,
        )
        
        assert engine.symbols == ["NVDA", "GLD"]
        assert engine.initial_capital == 100000.0

    def test_multi_asset_engine_run(self):
        bars_nvda = [
            Bar("NVDA", datetime(2025, 1, 2), 134, 136, 133, 136, 1000000),
            Bar("NVDA", datetime(2025, 1, 3), 136, 137, 135, 137, 1000000),
        ]
        
        bars_gld = [
            Bar("GLD", datetime(2025, 1, 2), 198, 200, 197, 199, 500000),
            Bar("GLD", datetime(2025, 1, 3), 199, 201, 198, 200, 500000),
        ]
        
        data = MockDataProvider({
            "NVDA": bars_nvda,
            "GLD": bars_gld,
        })
        
        class BuyAndHoldMulti(Strategy):
            def __init__(self):
                super().__init__()
                self.bought = False
            
            def on_bar(self, bar):
                if not self.bought and bar.symbol == "NVDA":
                    self.bought = True
                    return Signal(symbol=bar.symbol, signal_type=SignalType.BUY, strength=1.0)
                return Signal(symbol=bar.symbol, signal_type=SignalType.HOLD)
        
        engine = MultiAssetBacktestEngine(
            data_provider=data,
            strategy=BuyAndHoldMulti(),
            symbols=["NVDA", "GLD"],
            initial_capital=100000.0,
        )
        
        result = engine.run()
        
        assert result.final_equity > 0
        assert result.num_trades >= 0