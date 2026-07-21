"""
Cache statistics.
"""


class CacheStatistics:

    def metrics(
        self,
        repository,
    ):

        return {
            "entries": len(
                repository.cache
            )
        }