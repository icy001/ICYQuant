"""
Streaming market data loader.
"""


class StreamingLoader:

    def __init__(
        self,
        provider,
    ):

        self.provider = provider

    def subscribe(
        self,
        symbol,
    ):

        return self.provider.subscribe(
            symbol,
        )