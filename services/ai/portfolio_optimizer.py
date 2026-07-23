"""
Portfolio optimization assistant.
"""


class PortfolioOptimizer:

    def __init__(
        self,
        ai_service,
    ):

        self.ai_service = ai_service

    def optimize(
        self,
        portfolio,
    ):

        prompt = f"""
        Optimize portfolio.

        Portfolio:

        {portfolio}

        """

        return self.ai_service.execute(
            prompt
        )