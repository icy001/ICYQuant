"""
Unified cache manager.
"""


class CacheManager:

    def __init__(
        self,
        l1,
        l2,
        metrics,
    ):

        self.l1 = l1

        self.l2 = l2

        self.metrics = metrics

    def get(
        self,
        key,
    ):

        value = self.l1.get(
            key,
        )

        if value is not None:

            self.metrics.record_hit()

            return value

        value = self.l2.get(
            key,
        )

        if value is not None:

            self.l1.put(
                key,
                value,
            )

            self.metrics.record_hit()

            return value

        self.metrics.record_miss()

        return None

    def put(
        self,
        key,
        value,
    ):

        self.l1.put(
            key,
            value,
        )

        self.l2.put(
            key,
            value,
        )