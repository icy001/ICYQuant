class PortfolioRepository:
    def __init__(self):
        self.results = {}

    def save(self, result):
        self.results[result.portfolio_id] = result

    def get(self, portfolio_id):
        return self.results.get(portfolio_id)