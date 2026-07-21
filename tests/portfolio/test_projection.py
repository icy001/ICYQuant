from services.portfolio import (
    PortfolioProjectionEngine,
    ProjectionBuilder,
    ProjectionRepository,
)


def test_projection():
    repository = ProjectionRepository()

    engine = PortfolioProjectionEngine(
        repository,
        ProjectionBuilder(),
    )

    projection = engine.project(
        "PORT-001",
        {
            "cash": 100000,
        },
    )

    assert projection.data["cash"] == 100000