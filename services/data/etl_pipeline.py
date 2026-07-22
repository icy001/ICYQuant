"""
ETL pipeline.
"""


class ETLPipeline:

    def extract(
        self,
        data,
    ):

        return data

    def transform(
        self,
        data,
    ):

        return data

    def load(
        self,
        data,
        repository,
    ):

        repository.save(
            data,
        )