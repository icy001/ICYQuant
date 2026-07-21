"""
Cache synchronizer.
"""


class CacheSynchronizer:

    def synchronize(
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