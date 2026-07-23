"""
AI stress testing assistant.
"""


class StressTestingAgent:

    def __init__(
        self,
        simulator,
        ai_service,
    ):

        self.simulator = simulator

        self.ai_service = ai_service

    def test(
        self,
        portfolio,
        scenario,
    ):

        result = self.simulator.simulate(
            portfolio,
            scenario,
        )

        return self.ai_service.execute(
            str(result)
        )