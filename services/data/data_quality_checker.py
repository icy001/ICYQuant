"""
Market data quality checker.
"""


class DataQualityChecker:

    def validate(
        self,
        records,
    ):

        return all(
            record is not None
            for record in records
        )