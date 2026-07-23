from services.ai import PortfolioContext


def test_portfolio_context():

    portfolio = PortfolioContext(
        "PF001",
        ["NVDA", "MSFT"],
        10000,
        {},
    )

    assert portfolio.portfolio_id == "PF001"