"""
Performance attribution agent.
"""


class PerformanceAttributionAgent:

    def __init__(
        self,
        performance_service,
        ai_service,
    ):

        self.performance_service = performance_service

        self.ai_service = ai_service

    def analyze(
        self,
        portfolio,
    ):

        attribution = self.performance_service.calculate(
            portfolio
        )

        return self.ai_service.execute(
            str(attribution)
        )