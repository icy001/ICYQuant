from services.portfolio_opt import *


def test_portfolio():

    repo = PortfolioRepository()

    service = PortfolioOptimizationService(repo)

    portfolio = Portfolio(

        "PORT001",

        "AI Semiconductor Portfolio",

        1000000

    )

    service.create(portfolio)

    result = service.query(
        "PORT001"
    )

    assert result.name == "AI Semiconductor Portfolio"
