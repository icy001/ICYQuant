"""
Position risk analysis agent.
"""


class PositionRiskAgent:

    def __init__(
        self,
        risk_engine,
        ai_service,
    ):

        self.risk_engine = risk_engine

        self.ai_service = ai_service

    def analyze(
        self,
        positions,
    ):

        risk = self.risk_engine.calculate(
            positions
        )

        return self.ai_service.execute(
            str(risk)
        )