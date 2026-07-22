"""
Historical data loader.
"""


class HistoricalLoader:

    def __init__(
        self,
        provider,
    ):

        self.provider = provider

    def load(
        self,
        symbol,
    ):

        return self.provider.fetch(
            symbol,
        )