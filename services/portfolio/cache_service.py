"""
Cache service.
"""


class CacheService:

    def __init__(
        self,
        cache,
    ):

        self.cache = cache

    def get(
        self,
        key,
    ):

        return self.cache.load(
            key,
        )

    def put(
        self,
        key,
        value,
    ):

        return self.cache.save(
            key,
            value,
        )