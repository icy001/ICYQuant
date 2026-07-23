"""
Portfolio risk engine.
"""


class PortfolioRiskEngine:

    def calculate(
        self,
        portfolio,
    ):

        return {
            "portfolio": portfolio,
            "risk_score": 0.0,
        }