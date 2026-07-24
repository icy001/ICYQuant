class PortfolioManager:

    def __init__(
        self,
        repository,
    ):
        self.repository = repository

    def create(
        self,
        portfolio,
    ):
        self.repository.save(
            portfolio
        )
        return portfolio

    def get(
        self,
        portfolio_id,
    ):
        return self.repository.find(
            portfolio_id
        )