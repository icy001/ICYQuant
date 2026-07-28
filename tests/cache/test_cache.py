from services.cache import *


def test_cache():

    service = CacheService(
        CacheRepository()
    )

    entry = CacheEntry(
        "NVDA",
        182.36,
        60
    )

    service.put(entry)

    result = service.get("NVDA")

    assert result.value == 182.36
