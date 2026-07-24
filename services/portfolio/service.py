class PortfolioService:

    def __init__(
        self,
        manager,
    ):
        self.manager = manager

    def create_portfolio(
        self,
        portfolio,
    ):
        return self.manager.create(
            portfolio
        )

    def query_portfolio(
        self,
        portfolio_id,
    ):
        return self.manager.get(
            portfolio_id
        )