from services.portfolio import (
    DomainRegistry,
    PortfolioBootstrap,
)


def test_domain_bootstrap():
    registry = DomainRegistry()

    registry.register(
        "cache",
        object(),
    )

    registry.register(
        "query",
        object(),
    )

    bootstrap = PortfolioBootstrap(
        registry,
    )

    assert bootstrap.initialize() == 2