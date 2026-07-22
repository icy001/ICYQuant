from datetime import datetime

from services.research import (
    Feature,
    FeatureRegistry,
)


def test_register_feature():

    registry = FeatureRegistry()

    feature = Feature(
        "F001",
        "Momentum20",
        "float",
        "20-day momentum",
        "v1",
        datetime.utcnow(),
    )

    registry.register(
        feature
    )

    assert registry.get(
        "F001"
    ).name == "Momentum20"