"""
Drawdown analysis.
"""


class DrawdownAnalyzer:
    def max_drawdown(
        self,
        drawdowns: list[float],
    ) -> float:
        return min(drawdowns, default=0.0)