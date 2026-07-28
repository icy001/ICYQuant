class PortfolioOptimizationService:

    def __init__(self, repository):

        self.repository = repository

    def create(self, portfolio):

        self.repository.save(portfolio)

    def query(self, portfolio_id):

        return self.repository.get(portfolio_id)
