"""
Market data ingestion service.
"""


class DataIngestionService:

    def __init__(
        self,
        loader,
        etl,
        checker,
        repository,
    ):

        self.loader = loader

        self.etl = etl

        self.checker = checker

        self.repository = repository

    def ingest(
        self,
        dataset,
    ):

        data = self.loader.load(
            dataset,
        )

        data = self.etl.extract(
            data,
        )

        data = self.etl.transform(
            data,
        )

        if not self.checker.validate(
            data,
        ):

            raise ValueError(
                "Invalid market data."
            )

        self.etl.load(
            data,
            self.repository,
        )

        return data