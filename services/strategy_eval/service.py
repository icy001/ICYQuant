class StrategyEvaluationService:

    def __init__(self, repository):

        self.repository = repository

    def register(self, strategy):

        self.repository.save(strategy)

    def query(self, strategy_id):

        return self.repository.get(strategy_id)
