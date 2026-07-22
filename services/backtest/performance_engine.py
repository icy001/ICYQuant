"""
Performance analytics engine.
"""

from .performance_metrics import PerformanceMetrics


class PerformanceEngine:

    def __init__(
        self,
        return_calculator,
        drawdown_analyzer,
        sharpe,
        sortino,
    ):

        self.return_calculator = return_calculator

        self.drawdown_analyzer = drawdown_analyzer

        self.sharpe = sharpe

        self.sortino = sortino


    def analyze(
        self,
        initial_equity,
        final_equity,
        equity_curve,
        mean_return,
        volatility,
        downside,
    ):

        return PerformanceMetrics(
            total_return=
                self.return_calculator.calculate(
                    initial_equity,
                    final_equity,
                ),
            annual_return=0.0,
            max_drawdown=
                self.drawdown_analyzer.calculate(
                    equity_curve,
                ),
            sharpe_ratio=
                self.sharpe.calculate(
                    mean_return,
                    volatility,
                ),
            sortino_ratio=
                self.sortino.calculate(
                    mean_return,
                    downside,
                ),
        )