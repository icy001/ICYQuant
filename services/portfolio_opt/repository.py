class PortfolioRepository:

    def __init__(self):

        self.data = {}

    def save(self, portfolio):

        self.data[
            portfolio.portfolio_id
        ] = portfolio

    def get(self, portfolio_id):

        return self.data.get(portfolio_id)
