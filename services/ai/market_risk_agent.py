"""
Market risk analysis agent.
"""


class MarketRiskAgent:

    def __init__(
        self,
        market_service,
        ai_service,
    ):

        self.market_service = market_service

        self.ai_service = ai_service

    def analyze(
        self,
        symbols,
    ):

        market_data = self.market_service.get(
            symbols
        )

        return self.ai_service.execute(
            str(market_data)
        )