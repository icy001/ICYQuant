from datetime import datetime

from services.research import (
    Factor,
    FactorCalculator,
)


def test_factor_calculator():

    factor = Factor(
        "FA001",
        "Momentum",
        "close / sma20",
        "v1",
        datetime.utcnow(),
    )

    calculator = FactorCalculator()

    result = calculator.calculate(
        factor,
        [1.0, 2.0, 3.0],
    )

    assert result["factor"] == "Momentum"