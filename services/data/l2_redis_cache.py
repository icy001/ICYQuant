"""
L2 redis cache abstraction.
"""


class L2RedisCache:

    def __init__(self):

        self._storage = {}

    def get(
        self,
        key,
    ):

        return self._storage.get(
            key,
        )

    def put(
        self,
        key,
        value,
    ):

        self._storage[key] = value