"""
Cache refresher.
"""


class CacheRefresher:

    def refresh(
        self,
        repository,
        key,
        value,
    ):

        repository.put(
            key,
            value,
        )

        return value