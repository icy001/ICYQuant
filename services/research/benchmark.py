"""
Benchmark comparison.
"""


class BenchmarkComparator:
    def excess_return(
        self,
        strategy: float,
        benchmark: float,
    ) -> float:
        return strategy - benchmark