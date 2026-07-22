"""
Batch market data loader.
"""


class BatchLoader:

    def __init__(
        self,
        provider,
    ):

        self.provider = provider

    def load(
        self,
        dataset,
    ):

        return self.provider.fetch(
            dataset,
        )