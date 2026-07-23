"""
AI risk committee workflow.
"""


class RiskCommittee:

    def __init__(
        self,
        agents,
    ):

        self.agents = agents

    def review(
        self,
        context,
    ):

        result = {}

        for name, agent in self.agents.items():

            result[name] = agent.analyze(
                context
            )

        return result