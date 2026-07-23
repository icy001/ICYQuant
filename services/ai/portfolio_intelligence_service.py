"""
Portfolio intelligence service.
"""


class PortfolioIntelligenceService:

    def __init__(
        self,
        intelligence_agent,
        optimizer,
    ):

        self.intelligence_agent = intelligence_agent

        self.optimizer = optimizer

    def evaluate(
        self,
        portfolio,
    ):

        analysis = self.intelligence_agent.analyze(
            portfolio
        )

        optimization = self.optimizer.optimize(
            portfolio
        )

        return {
            "analysis": analysis,
            "optimization": optimization,
        }