from services.intelligence import *


def test_registry():

    registry = IntelligenceRegistry()

    dataset = Dataset(

        "DATA001",

        "MARKET_DATA",

        "v1"

    )

    registry.register(
        "market",
        dataset
    )

    result = registry.get(
        "market"
    )

    assert result.name == "MARKET_DATA"
