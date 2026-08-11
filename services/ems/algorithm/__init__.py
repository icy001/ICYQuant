"""Algorithm Execution Framework — Strategy abstraction and algorithm implementations.

Package exports::

    from services.ems.algorithm import (
        ExecutionStrategy,
        StrategyRegistry,
        TWAPStrategy,
        VWAPStrategy,
        POVStrategy,
        IcebergStrategy,
        ArrivalPriceStrategy,
        AdaptiveStrategy,
        ExecutionSimulator,
        BacktestAdapter,
    )
"""

from __future__ import annotations

from services.ems.algorithm.execution_strategy import ExecutionStrategy
from services.ems.algorithm.strategy_registry import StrategyRegistry
from services.ems.algorithm.twap import TWAPStrategy
from services.ems.algorithm.vwap import VWAPStrategy
from services.ems.algorithm.pov import POVStrategy
from services.ems.algorithm.iceberg import IcebergStrategy
from services.ems.algorithm.arrival_price import ArrivalPriceStrategy
from services.ems.algorithm.adaptive import AdaptiveStrategy
from services.ems.algorithm.simulator import ExecutionSimulator
from services.ems.algorithm.backtest_adapter import BacktestAdapter

__all__ = [
    "ExecutionStrategy",
    "StrategyRegistry",
    "TWAPStrategy",
    "VWAPStrategy",
    "POVStrategy",
    "IcebergStrategy",
    "ArrivalPriceStrategy",
    "AdaptiveStrategy",
    "ExecutionSimulator",
    "BacktestAdapter",
]
