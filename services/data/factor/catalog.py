"""
Alpha factor catalog.
"""


class FactorCatalog:
    def __init__(self):
        self.factors = {}

    def register(
        self,
        factor,
    ):
        self.factors[factor.name] = factor

    def get(
        self,
        name,
    ):
        return self.factors.get(name)