"""
Alpha research agent.
"""


class AlphaResearchAgent:

    def __init__(
        self,
        research_service,
        ai_service,
    ):

        self.research_service = research_service

        self.ai_service = ai_service

    def discover(
        self,
        query,
    ):

        research = self.research_service.search(
            query
        )

        return self.ai_service.execute(
            str(research)
        )