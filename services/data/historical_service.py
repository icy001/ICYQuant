"""
Historical market data service.
"""


class HistoricalService:

    def __init__(
        self,
        pipeline,
    ):

        self.pipeline = pipeline

    def sync(
        self,
        symbol,
    ):

        return self.pipeline.ingest(
            symbol,
        )