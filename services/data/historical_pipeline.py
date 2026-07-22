"""
Historical market data pipeline.
"""


class HistoricalPipeline:

    def __init__(
        self,
        loader,
        validator,
        repository,
    ):

        self.loader = loader
        self.validator = validator
        self.repository = repository

    def ingest(
        self,
        symbol,
    ):

        records = self.loader.load(
            symbol,
        )

        if not self.validator.validate(
            records,
        ):

            raise ValueError(
                "Historical data validation failed."
            )

        self.repository.save(
            symbol,
            records,
        )

        return records