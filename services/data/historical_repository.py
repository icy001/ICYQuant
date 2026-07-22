"""
Historical market data repository.
"""


class HistoricalRepository:

    def __init__(self):

        self._storage = {}

    def save(
        self,
        symbol,
        bars,
    ):

        self._storage[symbol] = bars

    def load(
        self,
        symbol,
    ):

        return self._storage.get(
            symbol,
            [],
        )