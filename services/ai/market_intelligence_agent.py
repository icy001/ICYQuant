"""
AI market intelligence agent.
"""


class MarketIntelligenceAgent:

    def __init__(
        self,
        ai_service,
        context_service,
    ):

        self.ai_service = ai_service

        self.context_service = context_service

    def analyze(
        self,
        market_context,
    ):

        context = self.context_service.build_context(
            market_context.timestamp
        )

        prompt = f"""
        Analyze current market environment.

        Market Context:

        {market_context}

        Additional Context:

        {context}

        """

        return self.ai_service.execute(
            prompt
        )