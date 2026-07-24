from services.portfolio import *


def test_portfolio_service():

    repository = PortfolioRepository()

    manager = PortfolioManager(
        repository
    )

    service = PortfolioService(
        manager
    )

    portfolio = Portfolio(
        "PF001",
        "ACC001",
        "AI Strategy"
    )

    service.create_portfolio(
        portfolio
    )

    result = service.query_portfolio(
        "PF001"
    )

    assert result.name == "AI Strategy"