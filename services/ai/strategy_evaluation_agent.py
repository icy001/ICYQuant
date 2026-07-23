"""
AI strategy evaluation agent.
"""


class StrategyEvaluationAgent:

    def __init__(
        self,
        ai_service,
    ):

        self.ai_service = ai_service

    def evaluate(
        self,
        strategy,
    ):

        prompt = f"""
        Evaluate quantitative strategy:

        {strategy}

        """

        return self.ai_service.execute(
            prompt
        )