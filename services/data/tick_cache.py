"""
Latest tick cache.
"""


class TickCache:

    def __init__(self):

        self._ticks = {}

    def update(
        self,
        tick,
    ):

        self._ticks[
            tick.symbol
        ] = tick

    def latest(
        self,
        symbol,
    ):

        return self._ticks.get(
            symbol
        )