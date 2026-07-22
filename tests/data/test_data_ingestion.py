from services.data import (
    ETLPipeline,
    DataQualityChecker,
)


def test_quality_checker():

    checker = DataQualityChecker()

    assert checker.validate(
        [
            {"close": 100},
            {"close": 101},
        ]
    )


def test_etl_extract():

    pipeline = ETLPipeline()

    data = [{"price": 1}]

    assert pipeline.extract(data) == data