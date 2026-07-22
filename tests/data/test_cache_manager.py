from services.data import (
    L1MemoryCache,
    L2RedisCache,
    CacheManager,
    CacheMetrics,
)


def test_cache_manager():

    manager = CacheManager(
        L1MemoryCache(),
        L2RedisCache(),
        CacheMetrics(),
    )

    manager.put(
        "AAPL",
        200,
    )

    assert manager.get(
        "AAPL",
    ) == 200