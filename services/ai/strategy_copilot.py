"""
Strategy Copilot.
"""


class StrategyCopilot:

    def __init__(
        self,
        ai_service,
    ):

        self.ai_service = ai_service

    def generate(
        self,
        requirement,
    ):

        prompt = f"""
        Create trading strategy:
        {requirement}
        """

        return self.ai_service.execute(
            prompt
        )