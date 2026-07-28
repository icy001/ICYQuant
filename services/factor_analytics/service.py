class FactorAnalyticsService:

    def __init__(self, repository):

        self.repository = repository

    def record(self, result):

        self.repository.save(result)

    def history(self):

        return self.repository.all()
