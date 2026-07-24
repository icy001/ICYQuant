from infrastructure.cache import *


def test_local_cache():

    cache = LocalCache()

    cache.put(

        "a",

        100,

    )

    assert cache.get(

        "a",

    ) == 100