"""
Earnings intelligence agent.
"""


class EarningsIntelligenceAgent:

    def __init__(
        self,
        earnings_service,
        ai_service,
    ):

        self.earnings_service = earnings_service

        self.ai_service = ai_service

    def analyze(
        self,
        symbol,
    ):

        earnings = self.earnings_service.get(
            symbol
        )

        return self.ai_service.execute(
            str(earnings)
        )