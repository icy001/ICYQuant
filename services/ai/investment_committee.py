"""
AI investment committee workflow.
"""


class InvestmentCommittee:

    def __init__(
        self,
        agents,
    ):

        self.agents = agents

    def review(
        self,
        portfolio,
    ):

        result = {}

        for name, agent in self.agents.items():

            result[name] = agent.analyze(
                portfolio
            )

        return result