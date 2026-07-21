from services.portfolio import (
    CacheRepository,
    ReadModelCache,
)


def test_cache():
    repository = CacheRepository()

    cache = ReadModelCache(
        repository,
    )

    cache.save(
        "PORT-001",
        {
            "nav": 1000000,
        },
    )

    assert cache.load(
        "PORT-001",
    )["nav"] == 1000000