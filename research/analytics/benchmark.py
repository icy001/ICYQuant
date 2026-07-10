from dataclasses import dataclass
from typing import List, Tuple
from datetime import datetime

from .metrics import calculate_total_return


@dataclass(frozen=True)
class BenchmarkResult:
    strategy_return: float
    benchmark_return: float
    alpha: float


class Benchmark:

    def __init__(self, name: str, equity_curve: List[Tuple[datetime, float]]):
        self.name = name
        self.equity_curve = equity_curve

    def calculate_return(self) -> float:
        if not self.equity_curve:
            return 0.0
        initial = self.equity_curve[0][1]
        final = self.equity_curve[-1][1]
        return calculate_total_return(initial, final)

    def compare(
        self,
        strategy_equity_curve: List[Tuple[datetime, float]]
    ) -> BenchmarkResult:
        strategy_return = 0.0
        if strategy_equity_curve:
            initial = strategy_equity_curve[0][1]
            final = strategy_equity_curve[-1][1]
            strategy_return = calculate_total_return(initial, final)

        benchmark_return = self.calculate_return()
        alpha = strategy_return - benchmark_return

        return BenchmarkResult(
            strategy_return=strategy_return,
            benchmark_return=benchmark_return,
            alpha=alpha
        )