from services.risk import (
    Exposure,
    ExposureRepository,
    ExposureAggregator,
)


def test_exposure():
    repository = ExposureRepository()
    repository.save(
        Exposure(
            "PORT-001",
            "AAPL",
            100000,
            "EQUITY",
        )
    )

    result = ExposureAggregator().aggregate(
        repository.list_all()
    )

    assert result["AAPL"] == 100000