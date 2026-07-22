"""
Concentration risk service.
"""


class ConcentrationService:

    def __init__(
        self,
        engine,
    ):

        self.engine = engine

    def calculate(
        self,
        weights,
    ):

        return self.engine.calculate(
            weights,
        )

    def check(
        self,
        weight,
        limit,
    ):

        return self.engine.check(
            weight,
            limit,
        )