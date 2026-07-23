"""
AI factor discovery agent.
"""


class FactorDiscoveryAgent:

    def __init__(
        self,
        ai_service,
        research_context,
    ):

        self.ai_service = ai_service

        self.research_context = research_context

    def discover(
        self,
        objective,
    ):

        context = self.research_context.build_context(
            objective
        )

        prompt = f"""
        Discover quantitative factors.

        Objective:

        {objective}

        Context:

        {context}

        """

        return self.ai_service.execute(
            prompt
        )