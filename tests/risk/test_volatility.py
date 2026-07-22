from services.risk import (
    HistoricalVolatilityCalculator,
)


def test_volatility():
    calculator = HistoricalVolatilityCalculator()

    result = calculator.calculate(
        [
            0.01,
            -0.02,
            0.03,
        ]
    )

    assert result > 0