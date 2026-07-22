from services.risk import (
    ConcentrationCalculator,
)


def test_concentration():
    calculator = ConcentrationCalculator()

    result = calculator.calculate(
        [
            0.2,
            0.5,
            0.3,
        ]
    )

    assert result == 0.5