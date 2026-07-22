"""
Exposure validator.
"""


class ExposureValidator:

    def validate(
        self,
        exposure,
        limit,
    ):

        return exposure <= limit.max_exposure