from pathlib import Path
import pytest

from research.data.csv_provider import CsvMarketDataProvider
from research.data.universe import Universe
from research.data.multi_asset_provider import MultiAssetDataProvider
from research.data.types import TimeFrame
from research.data.snapshot import MarketSnapshot
from research.backtest.timeline import Timeline
from research.events.market import MarketEvent
from research.strategy.multi_asset_base import MultiAssetStrategy
from research.orders.signal import PortfolioSignal
from research.backtest.multi_asset_runner import MultiAssetBacktestRunner


class EqualWeightStrategy(MultiAssetStrategy):

    def on_market(self, snapshot):
        if not snapshot.bars:
            return []

        weight = 1 / len(snapshot.bars)

        return [
            PortfolioSignal(
                symbol=symbol,
                target_weight=weight
            )
            for symbol in snapshot.bars.keys()
        ]


class TestMultiAssetBacktest:

    def test_multi_asset_backtest_with_equal_weight(self):
        data_root = Path(__file__).parent.parent / "research" / "data" / "sample"

        universe = Universe(["NVDA", "GLD", "QQQI"])

        providers = {
            "NVDA": CsvMarketDataProvider(data_root),
            "GLD": CsvMarketDataProvider(data_root),
            "QQQI": CsvMarketDataProvider(data_root),
        }

        multi_provider = MultiAssetDataProvider(providers)
        datasets = multi_provider.load(universe, TimeFrame.D1)

        timeline = Timeline()
        timeline.merge(datasets)

        events = []
        for timestamp, market_data in timeline:
            snapshot = MarketSnapshot(timestamp=timestamp, bars=market_data)
            event = MarketEvent(timestamp=timestamp, snapshot=snapshot)
            events.append(event)

        assert len(events) == 10

        strategy = EqualWeightStrategy()
        strategy.initialize()

        runner = MultiAssetBacktestRunner(
            strategy=strategy,
            initial_cash=100000.0
        )

        portfolio = runner.run(events)

        assert len(portfolio.holdings.positions) == 3
        assert "NVDA" in portfolio.holdings.positions
        assert "GLD" in portfolio.holdings.positions
        assert "QQQI" in portfolio.holdings.positions

        nvda_position = portfolio.holdings.positions["NVDA"]
        gld_position = portfolio.holdings.positions["GLD"]
        qqq_position = portfolio.holdings.positions["QQQI"]

        assert nvda_position.quantity > 0
        assert gld_position.quantity > 0
        assert qqq_position.quantity > 0

        assert portfolio.cash >= -1e-10

    def test_multi_asset_backtest_single_asset(self):
        data_root = Path(__file__).parent.parent / "research" / "data" / "sample"

        universe = Universe(["NVDA"])

        providers = {
            "NVDA": CsvMarketDataProvider(data_root),
        }

        multi_provider = MultiAssetDataProvider(providers)
        datasets = multi_provider.load(universe, TimeFrame.D1)

        timeline = Timeline()
        timeline.merge(datasets)

        events = []
        for timestamp, market_data in timeline:
            snapshot = MarketSnapshot(timestamp=timestamp, bars=market_data)
            event = MarketEvent(timestamp=timestamp, snapshot=snapshot)
            events.append(event)

        strategy = EqualWeightStrategy()
        strategy.initialize()

        runner = MultiAssetBacktestRunner(
            strategy=strategy,
            initial_cash=100000.0
        )

        portfolio = runner.run(events)

        assert len(portfolio.holdings.positions) == 1
        assert "NVDA" in portfolio.holdings.positions

    def test_multi_asset_backtest_empty_events(self):
        strategy = EqualWeightStrategy()
        strategy.initialize()

        runner = MultiAssetBacktestRunner(
            strategy=strategy,
            initial_cash=100000.0
        )

        portfolio = runner.run([])

        assert len(portfolio.holdings.positions) == 0
        assert portfolio.cash == 100000.0