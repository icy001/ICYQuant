"""
L1 in-memory cache.
"""


class L1MemoryCache:

    def __init__(self):

        self._cache = {}

    def get(
        self,
        key,
    ):

        return self._cache.get(
            key,
        )

    def put(
        self,
        key,
        value,
    ):

        self._cache[key] = value