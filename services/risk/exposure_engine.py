"""
Exposure risk engine.
"""


class ExposureEngine:

    def __init__(
        self,
        repository,
        aggregator,
        validator,
    ):

        self.repository = repository

        self.aggregator = aggregator

        self.validator = validator

    def calculate(self):

        return self.aggregator.aggregate(
            self.repository.list_all()
        )

    def check(
        self,
        exposure,
        limit,
    ):

        return self.validator.validate(
            exposure,
            limit,
        )