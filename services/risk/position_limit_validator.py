"""
Position limit validator.
"""


class PositionLimitValidator:

    def validate(
        self,
        exposure,
        limit,
    ):

        return exposure <= limit.max_quantity