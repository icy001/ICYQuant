from services.risk import (
    PositionLimit,
    PositionLimitRepository,
    PositionExposureCalculator,
    PositionLimitValidator,
    PositionLimitEngine,
)


def test_position_limit():
    repository = PositionLimitRepository()

    repository.save(
        PositionLimit(
            "AAPL",
            1000,
        )
    )

    engine = PositionLimitEngine(
        repository,
        PositionExposureCalculator(),
        PositionLimitValidator(),
    )

    assert engine.check(
        "AAPL",
        500,
        200,
    )