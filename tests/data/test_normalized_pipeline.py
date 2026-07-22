from services.data import (
    DataNormalizer,
    SymbolMapper,
    TimezoneConverter,
    CorporateActionAdjuster,
    NormalizedPipeline,
)


def test_normalize():
    mapper = SymbolMapper()
    mapper.register(
        "AAPL.US",
        "AAPL",
    )

    pipeline = NormalizedPipeline(
        DataNormalizer(),
        mapper,
        TimezoneConverter(),
        CorporateActionAdjuster(),
    )

    result = pipeline.process(
        {
            "Symbol": "AAPL.US",
            "Close": 200,
        }
    )

    assert result["symbol"] == "AAPL"