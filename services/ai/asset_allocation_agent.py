"""
Asset allocation intelligence agent.
"""


class AssetAllocationAgent:

    def __init__(
        self,
        ai_service,
    ):

        self.ai_service = ai_service

    def recommend(
        self,
        portfolio,
    ):

        prompt = f"""
        Recommend asset allocation.

        Portfolio:

        {portfolio}

        """

        return self.ai_service.execute(
            prompt
        )