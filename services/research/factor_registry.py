"""
Factor registry.
"""


class FactorRegistry:

    def __init__(self):

        self._factors = {}

    def register(
        self,
        factor,
    ):

        self._factors[
            factor.factor_id
        ] = factor

    def get(
        self,
        factor_id,
    ):

        return self._factors.get(
            factor_id
        )

    def list_all(self):

        return list(
            self._factors.values()
        )