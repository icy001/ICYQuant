"""
AI risk intelligence agent.
"""


class RiskAgent:

    def __init__(
        self,
        ai_service,
        context_service,
    ):

        self.ai_service = ai_service

        self.context_service = context_service

    def analyze(
        self,
        risk_context,
    ):

        context = self.context_service.build_context(
            risk_context.portfolio_id
        )

        prompt = f"""
        Analyze portfolio risk.

        Risk Context:

        {risk_context}

        Additional Context:

        {context}

        """

        return self.ai_service.execute(
            prompt
        )