"""
Data quality metrics.
"""


class DataQualityMetrics:

    def calculate(
        self,
        total,
        invalid,
    ):

        if total == 0:

            return 1.0

        return (
            total - invalid
        ) / total