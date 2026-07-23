"""
Risk intelligence agent.
"""


class RiskIntelligenceAgent:

    def __init__(
        self,
        risk_service,
        ai_service,
    ):

        self.risk_service = risk_service

        self.ai_service = ai_service

    def evaluate(
        self,
        portfolio,
    ):

        risk = self.risk_service.analyze(
            portfolio
        )

        return self.ai_service.execute(
            str(risk)
        )