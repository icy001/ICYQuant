from pathlib import Path
from datetime import date

from research.experiments.metadata import ExperimentMetadata
from research.experiments.experiment import Experiment
from research.experiments.registry import ExperimentRegistry

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


def run_experiment():
    print("=" * 50)
    print("ICYQuant Research Experiment Framework")
    print("=" * 50)
    print()

    registry = ExperimentRegistry()

    metadata = ExperimentMetadata(
        name="NVDA_AI_Portfolio_v1",
        strategy="EqualWeightStrategy",
        symbols=["NVDA", "GLD", "QQQI"],
        start=date(2025, 1, 1),
        end=date(2025, 1, 31),
        parameters={"initial_capital": 100000}
    )

    experiment = Experiment(metadata=metadata)

    print(f"Experiment: {metadata.name}")
    print(f"Strategy: {metadata.strategy}")
    print(f"Symbols: {', '.join(metadata.symbols)}")
    print(f"Date Range: {metadata.start} to {metadata.end}")
    print(f"Parameters: {metadata.parameters}")
    print()

    data_root = Path(__file__).parent.parent / "tests" / "research" / "data" / "sample"

    universe = Universe(metadata.symbols)

    providers = {
        symbol: CsvMarketDataProvider(data_root)
        for symbol in metadata.symbols
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
        initial_cash=metadata.parameters["initial_capital"]
    )

    portfolio = runner.run(events)

    final_equity = portfolio.equity({
        symbol: portfolio.holdings.positions[symbol].average_price
        for symbol in metadata.symbols
    })

    total_return = (final_equity - metadata.parameters["initial_capital"]) / metadata.parameters["initial_capital"]

    result = {
        "return": round(total_return, 4),
        "final_equity": round(final_equity, 2),
        "num_positions": len(portfolio.holdings.positions),
    }

    experiment.complete(result)

    registry.register(experiment)

    print("=" * 50)
    print("Experiment Results")
    print("=" * 50)
    print()
    print(f"Final Equity: ${result['final_equity']:,.2f}")
    print(f"Total Return: {result['return']:.2%}")
    print(f"Number of Positions: {result['num_positions']}")
    print()

    for symbol, position in portfolio.holdings.positions.items():
        print(f"  {symbol}: {position.quantity:.2f} shares @ ${position.average_price:.2f}")

    print()
    print(f"Experiments in Registry: {len(registry)}")
    print("=" * 50)


if __name__ == "__main__":
    run_experiment()