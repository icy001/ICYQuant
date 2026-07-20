"""
Performance attribution engine.
"""


class PerformanceAttributionEngine:
    def __init__(
        self,
        strategy_analyzer,
        pnl_calculator,
    ):
        self.strategy_analyzer = strategy_analyzer
        self.pnl_calculator = pnl_calculator

    def analyze(
        self,
        strategies,
    ):
        pnl = self.strategy_analyzer.analyze(strategies)
        contribution = self.pnl_calculator.calculate(pnl)
        return {
            "pnl": pnl,
            "contribution": contribution,
        }