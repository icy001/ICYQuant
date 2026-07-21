"""
Enterprise risk pipeline.
"""


class RiskPipeline:

    def __init__(
        self,
        platform,
    ):

        self.platform = platform

    def execute(
        self,
        context,
    ):

        return {
            "pre_trade":
                self.platform.pre_trade,
            "margin":
                self.platform.margin,
            "leverage":
                self.platform.leverage,
            "exposure":
                self.platform.exposure,
            "concentration":
                self.platform.concentration,
            "liquidity":
                self.platform.liquidity,
            "volatility":
                self.platform.volatility,
            "stress":
                self.platform.stress,
            "scenario":
                self.platform.scenario,
        }