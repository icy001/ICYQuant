"""
AI risk reporting automation.
"""


class RiskReportGenerator:

    def __init__(
        self,
        ai_service,
    ):

        self.ai_service = ai_service

    def generate(
        self,
        risk_result,
    ):

        prompt = f"""
        Generate risk report:

        {risk_result}

        """

        return self.ai_service.execute(
            prompt
        )