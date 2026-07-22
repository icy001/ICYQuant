from services.data import (
    HistoricalValidator,
)


def test_historical_validator():

    validator = HistoricalValidator()

    assert validator.validate(
        [
            {
                "open": 1,
                "high": 2,
                "low": 0.5,
                "close": 1.5,
                "volume": 100,
            }
        ]
    )