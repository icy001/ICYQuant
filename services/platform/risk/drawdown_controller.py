"""
Drawdown control system.
"""


class DrawdownController:

    def check(
        self,
        equity,
        peak,
    ):

        drawdown = (
            peak - equity
        ) / peak

        return {
            "drawdown":
                drawdown,
            "blocked":
                drawdown > 0.2,
        }