"""
Risk intelligence service.
"""


class RiskIntelligenceService:

    def __init__(
        self,
        risk_agent,
        report_generator,
    ):

        self.risk_agent = risk_agent

        self.report_generator = report_generator

    def evaluate(
        self,
        context,
    ):

        risk = self.risk_agent.analyze(
            context
        )

        report = self.report_generator.generate(
            risk
        )

        return {
            "risk": risk,
            "report": report,
        }