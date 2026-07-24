class PortfolioRepository:

    def __init__(self):
        self.portfolios = {}

    def save(
        self,
        portfolio,
    ):
        self.portfolios[
            portfolio.portfolio_id
        ] = portfolio

    def find(
        self,
        portfolio_id,
    ):
        return self.portfolios.get(
            portfolio_id
        )