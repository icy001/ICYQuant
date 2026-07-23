"""
Autonomous investment workflow.
"""


class AutonomousInvestmentWorkflow:

    def __init__(
        self,
        engine,
    ):

        self.engine = engine

    def run(
        self,
        objective,
    ):

        workflow = [
            {
                "name": "market",
                "agent": "market",
                "input": objective,
            },
            {
                "name": "research",
                "agent": "research",
                "input": objective,
            },
            {
                "name": "risk",
                "agent": "risk",
                "input": objective,
            },
        ]

        return self.engine.execute(
            workflow
        )