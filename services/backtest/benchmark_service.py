"""
Benchmark service.
"""


class BenchmarkService:
    def __init__(
        self,
        alpha,
        beta,
        attribution,
    ):
        self.alpha = alpha
        self.beta = beta
        self.attribution = attribution

    def analyze(
        self,
        strategy_return,
        benchmark_return,
    ):
        return {
            "alpha": self.alpha.calculate(strategy_return, benchmark_return),
        }