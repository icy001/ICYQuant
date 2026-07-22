"""
Market data service.
"""


class DataService:

    def __init__(
        self,
        access_layer,
    ):

        self.access_layer = access_layer

    def get_market_data(
        self,
        symbol,
    ):

        return self.access_layer.load(
            symbol,
        )