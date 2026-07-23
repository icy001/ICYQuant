"""
Portfolio intelligence agent.
"""


class PortfolioIntelligenceAgent:

    def __init__(
        self,
        ai_service,
        context_service,
    ):

        self.ai_service = ai_service

        self.context_service = context_service

    def analyze(
        self,
        portfolio,
    ):

        context = self.context_service.build_context(
            portfolio.portfolio_id
        )

        prompt = f"""
        Analyze investment portfolio.

        Portfolio:

        {portfolio}

        Context:

        {context}

        """

        return self.ai_service.execute(
            prompt
        )