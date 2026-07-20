from services.portfolio import (
    Portfolio,
    PortfolioRepository,
    PortfolioStatus,
    PortfolioAggregate,
    PortfolioService,
)


def test_create_portfolio():
    repository = PortfolioRepository()

    portfolio = Portfolio(
        portfolio_id="pf-001",
        name="main",
        status="ACTIVE",
    )

    repository.save(portfolio)

    result = repository.get("pf-001")

    assert result.name == "main"


def test_portfolio_not_found():
    repository = PortfolioRepository()

    assert repository.get("pf-999") is None


def test_portfolio_status_enum():
    assert PortfolioStatus.ACTIVE.value == "ACTIVE"
    assert PortfolioStatus.CLOSED.value == "CLOSED"
    assert PortfolioStatus.SUSPENDED.value == "SUSPENDED"


def test_portfolio_aggregate_activate():
    portfolio = Portfolio(
        portfolio_id="pf-002",
        name="test",
        status="SUSPENDED",
    )

    aggregate = PortfolioAggregate(portfolio)
    aggregate.activate()

    assert portfolio.status == "ACTIVE"


def test_portfolio_aggregate_close():
    portfolio = Portfolio(
        portfolio_id="pf-003",
        name="test",
        status="ACTIVE",
    )

    aggregate = PortfolioAggregate(portfolio)
    aggregate.close()

    assert portfolio.status == "CLOSED"


def test_portfolio_service():
    repository = PortfolioRepository()
    service = PortfolioService(repository)

    portfolio = Portfolio(
        portfolio_id="pf-004",
        name="service_test",
        status="ACTIVE",
    )

    result = service.create(portfolio)

    assert result == portfolio
    assert repository.get("pf-004") == portfolio