from datetime import datetime

import pytest

from services.data.feature import (
    Feature,
    OnlineFeatureStore,
    OfflineFeatureStore,
    FeatureService,
    FeatureDefinition,
    FeatureRegistry,
    FeatureVersion,
)


@pytest.mark.asyncio
async def test_online_feature():
    store = OnlineFeatureStore()

    feature = Feature(
        symbol="NVDA",
        name="momentum",
        value=0.25,
        timestamp=datetime.now(),
    )

    await store.put(feature)

    result = await store.get("NVDA", "momentum")

    assert result.value == 0.25


@pytest.mark.asyncio
async def test_offline_store():
    store = OfflineFeatureStore()

    feature1 = Feature("AAPL", "momentum", 0.15, datetime.now())
    feature2 = Feature("NVDA", "momentum", 0.25, datetime.now())

    await store.save(feature1)
    await store.save(feature2)

    results = await store.query("NVDA")

    assert len(results) == 1
    assert results[0].value == 0.25


@pytest.mark.asyncio
async def test_feature_service():
    offline = OfflineFeatureStore()
    online = OnlineFeatureStore()
    service = FeatureService(offline, online)

    feature = Feature("NVDA", "volatility", 0.35, datetime.now())

    await service.publish(feature)

    offline_result = await offline.query("NVDA")
    online_result = await online.get("NVDA", "volatility")

    assert len(offline_result) == 1
    assert online_result.value == 0.35


def test_feature_registry():
    registry = FeatureRegistry()

    definition = FeatureDefinition(
        name="momentum_20d",
        description="20 day return",
        owner="research",
    )

    registry.register(definition)

    result = registry.get("momentum_20d")

    assert result.owner == "research"


def test_feature_version():
    version = FeatureVersion(
        feature_name="momentum",
        version="v2",
    )

    assert version.version == "v2"