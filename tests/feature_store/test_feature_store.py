from services.feature_store import *


def test_feature_registry():

    registry = FeatureRegistry()

    feature = Feature(

        "F001",

        "RSI14",

        65.5

    )

    registry.register(feature)

    result = registry.get(
        "RSI14"
    )

    assert result.value == 65.5
