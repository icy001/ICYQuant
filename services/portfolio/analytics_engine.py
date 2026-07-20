"""
Portfolio analytics engine.
"""


class PortfolioAnalyticsEngine:
    def __init__(
        self,
        kpi_calculator,
    ):
        self.kpi_calculator = kpi_calculator

    def generate(
        self,
        nav_history,
    ):
        start = nav_history[0]
        end = nav_history[-1]

        return {
            "return": self.kpi_calculator.calculate_return(start, end),
            "current_nav": end,
        }