class AIResearchService:

    def __init__(
        self,
        agent,
        repository
    ):

        self.agent = agent

        self.repository = repository

    def research(self, request):

        result = self.agent.analyze(
            request
        )

        self.repository.save(
            result
        )

        return result
