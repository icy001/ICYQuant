from services.risk import (
    MarginRequirement,
    MarginRepository,
    InitialMarginCalculator,
    MarginValidator,
    MarginEngine,
)


def test_margin():
    repository = MarginRepository()

    repository.save(
        MarginRequirement(
            "AAPL",
            0.2,
            0.1,
        )
    )

    engine = MarginEngine(
        repository,
        InitialMarginCalculator(),
        MarginValidator(),
    )

    assert engine.check(
        "AAPL",
        100000,
        50000,
    )