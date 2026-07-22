"""
Market data stream.
"""


class MarketDataStream:

    def __init__(self):

        self._subscribers = []

    def subscribe(
        self,
        subscriber,
    ):

        self._subscribers.append(
            subscriber
        )

    def publish(
        self,
        tick,
    ):

        for subscriber in self._subscribers:

            subscriber.on_tick(
                tick
            )