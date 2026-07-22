"""
Real-time market data service.
"""


class RealtimeMarketDataService:

    def __init__(
        self,
        publisher,
        cache,
    ):

        self.publisher = publisher
        self.cache = cache

    def process(
        self,
        tick,
    ):

        self.cache.update(
            tick
        )

        self.publisher.publish(
            tick
        )

        return tick