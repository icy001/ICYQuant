from pathlib import Path

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
from research.analytics.report import PerformanceReport


class EqualWeightStrategy(MultiAssetStrategy):

    def on_market(self, snapshot: MarketSnapshot):
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


def run():
    data_root = Path(__file__).parent.parent / "tests" / "research" / "data" / "sample"

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

    strategy = EqualWeightStrategy()
    strategy.initialize()

    runner = MultiAssetBacktestRunner(
        strategy=strategy,
        initial_cash=100000.0
    )

    portfolio = runner.run(events)

    print("=== Equal Weight Strategy Backtest Results ===")
    print(f"Initial Cash: ${portfolio.initial_cash:,.2f}")
    print(f"Final Cash: ${portfolio.cash:,.2f}")
    print(f"Number of Positions: {len(portfolio.holdings.positions)}")
    
    for symbol, position in portfolio.holdings.positions.items():
        print(f"  {symbol}: {position.quantity:.2f} shares @ ${position.average_price:.2f}")

    if portfolio.equity_curve:
        final_equity = portfolio.equity_curve[-1][1]
        print(f"Final Equity: ${final_equity:,.2f}")
        print(f"Total Return: {(final_equity - portfolio.initial_cash) / portfolio.initial_cash * 100:.2f}%")


if __name__ == "__main__":
    run()