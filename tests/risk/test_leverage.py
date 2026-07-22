from services.risk import (
    LeverageRule,
    LeverageRepository,
    LeverageCalculator,
    LeverageValidator,
    LeverageEngine,
)


def test_leverage():
    repository = LeverageRepository()

    repository.save(
        LeverageRule(
            "ACC-001",
            5,
        )
    )

    engine = LeverageEngine(
        repository,
        LeverageCalculator(),
        LeverageValidator(),
    )

    result = engine.check(
        "ACC-001",
        500000,
        100000,
    )

    assert result.approved