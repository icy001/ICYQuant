from services.data import (
    FeatureStore,
    FeatureCache,
    FeatureRetrievalService,
)


def test_feature_store():

    store = FeatureStore()

    cache = FeatureCache()

    service = FeatureRetrievalService(
        store,
        cache,
    )

    store.put(
        "AAPL",
        "volatility",
        0.25,
    )

    assert service.get(
        "AAPL",
        "volatility",
    ) == 0.25