"""
Market data gateway.
"""


class MarketDataGateway:

    def __init__(self):
        self.listeners = []

    def subscribe(
        self,
        listener,
    ):
        self.listeners.append(listener)

    def publish(
        self,
        tick,
    ):
        for listener in self.listeners:
            listener.handle(tick)