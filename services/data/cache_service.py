"""
Unified cache service.
"""


class CacheService:

    def __init__(
        self,
        manager,
    ):

        self.manager = manager

    def get(
        self,
        key,
    ):

        return self.manager.get(
            key,
        )

    def put(
        self,
        key,
        value,
    ):

        self.manager.put(
            key,
            value,
        )