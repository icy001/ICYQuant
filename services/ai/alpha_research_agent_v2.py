"""
Alpha Research Agent v2.
"""


class AlphaResearchAgentV2:

    def __init__(
        self,
        factor_agent,
        feature_agent,
        evaluation_agent,
    ):

        self.factor_agent = factor_agent

        self.feature_agent = feature_agent

        self.evaluation_agent = evaluation_agent

    def research(
        self,
        objective,
    ):

        factors = self.factor_agent.discover(
            objective
        )

        features = self.feature_agent.generate(
            factors
        )

        evaluation = self.evaluation_agent.evaluate(
            features
        )

        return {
            "factors": factors,
            "features": features,
            "evaluation": evaluation,
        }