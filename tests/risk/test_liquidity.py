from services.risk import (
    LiquidityProfile,
    LiquidityRepository,
    LiquidityCalculator,
)


def test_liquidity():
    repository = LiquidityRepository()

    repository.save(
        LiquidityProfile(
            "AAPL",
            1000000,
            50000000,
        )
    )

    calculator = LiquidityCalculator()

    ratio = calculator.calculate_volume_ratio(
        100000,
        1000000,
    )

    assert ratio == 0.1