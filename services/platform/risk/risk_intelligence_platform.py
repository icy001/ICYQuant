"""
Institutional risk intelligence platform.
"""


class RiskIntelligencePlatform:

    def __init__(
        self,
        risk_center,
    ):

        self.center = risk_center

    def evaluate(
        self,
        portfolio,
    ):

        return self.center.decide(
            portfolio
        )