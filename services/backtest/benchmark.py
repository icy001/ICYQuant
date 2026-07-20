"""
Benchmark comparison.
"""


class BenchmarkComparator:
    def compare(
        self,
        strategy_return: float,
        benchmark_return: float,
    ) -> float:
        return strategy_return - benchmark_return