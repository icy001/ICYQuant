from services.portfolio import (
    CacheRepository,
    ReadModelCache,
    CacheService,
    PortfolioQueryGateway,
    QueryAggregator,
    QueryAuthorizer,
    QueryRequest,
    QueryRouter,
)


def test_query_gateway():
    repository = CacheRepository()

    cache = ReadModelCache(repository)

    service = CacheService(cache)

    service.put(
        "PORT-001",
        {"cash": 1000},
    )

    gateway = PortfolioQueryGateway(
        QueryRouter(),
        QueryAuthorizer(),
        QueryAggregator(),
    )

    response = gateway.query(
        "admin",
        QueryRequest(
            "Q-001",
            "PORT-001",
            "SUMMARY",
        ),
        service,
    )

    assert response.success

    assert response.data["cash"] == 1000