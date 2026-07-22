"""
Market data catalog.
"""


class MarketDataCatalog:

    def __init__(self):

        self._sources = {}

    def register(
        self,
        source,
    ):

        self._sources[
            source.source_id
        ] = source

    def get(
        self,
        source_id,
    ):

        return self._sources.get(
            source_id
        )

    def list_all(self):

        return list(
            self._sources.values()
        )