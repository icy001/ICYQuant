"""
AI strategy generator.
"""


class StrategyGenerator:

    def __init__(
        self,
        ai_service,
    ):

        self.ai_service = ai_service

    def generate(
        self,
        alpha,
    ):

        prompt = f"""
        Generate quantitative strategy.

        Alpha:

        {alpha}

        """

        return self.ai_service.execute(
            prompt
        )