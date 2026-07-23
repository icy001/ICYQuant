"""
Market analysis agent.
"""


class MarketAnalysisAgent:

    def __init__(
        self,
        market_data,
        ai_service,
    ):

        self.market_data = market_data

        self.ai_service = ai_service

    def analyze(
        self,
        symbol,
    ):

        data = self.market_data.get(
            symbol
        )

        return self.ai_service.execute(
            str(data)
        )