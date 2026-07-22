"""
Visualization generator.
"""


class VisualizationGenerator:

    def generate(
        self,
        metrics,
    ):

        return {
            "charts": [
                "equity_curve",
                "drawdown",
                "ic_curve",
            ],
            "metrics": metrics,
        }