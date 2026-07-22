"""
Maximum drawdown analyzer.
"""


class DrawdownAnalyzer:

    def calculate(
        self,
        equity_curve,
    ):

        peak = equity_curve[0]

        max_drawdown = 0.0

        for equity in equity_curve:

            peak = max(
                peak,
                equity,
            )

            drawdown = (
                peak -
                equity
            ) / peak

            max_drawdown = max(
                max_drawdown,
                drawdown,
            )

        return max_drawdown