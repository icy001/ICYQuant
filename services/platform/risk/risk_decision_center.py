"""
Risk decision center.
"""


class RiskDecisionCenter:

    def __init__(
        self,
        var_engine,
        stress_engine,
        drawdown,
    ):

        self.var = var_engine

        self.stress = stress_engine

        self.drawdown = drawdown

    def decide(
        self,
        portfolio,
    ):

        return {
            "var":
                self.var.calculate(
                    portfolio
                ),
            "stress":
                self.stress.simulate(
                    "default"
                ),
        }