from datetime import datetime
from pathlib import Path

from research.data.csv_provider import CsvMarketDataProvider
from research.data.types import TimeFrame
from research.strategy.moving_average import MovingAverageCrossStrategy
from research.strategy.buy_and_hold import BuyAndHoldStrategy
from research.backtest.runner import BacktestRunner


def main():
    DATA_DIR = Path(__file__).parent.parent / "tests" / "research" / "data" / "sample"
    
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
    
    print(result)


if __name__ == "__main__":
    main()