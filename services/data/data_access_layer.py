"""
Data access layer.
"""


class DataAccessLayer:

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