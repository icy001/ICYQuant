"""
Position limit repository.
"""


class PositionLimitRepository:

    def __init__(self):

        self.limits = {}

    def save(
        self,
        limit,
    ):

        self.limits[
            limit.symbol
        ] = limit

    def load(
        self,
        symbol,
    ):

        return self.limits.get(
            symbol
        )