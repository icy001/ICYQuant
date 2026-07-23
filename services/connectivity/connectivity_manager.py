"""
Connectivity manager.
"""


class ConnectivityManager:

    def __init__(
        self,
        market,
        exchange,
    ):
        self.market = market
        self.exchange = exchange

    def start(self):
        return {
            "market":
                "ready",
            "exchange":
                self.exchange.connect()
        }