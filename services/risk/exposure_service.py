"""
Exposure service.
"""


class ExposureService:

    def __init__(
        self,
        engine,
    ):

        self.engine = engine

    def aggregate(self):

        return self.engine.calculate()

    def validate(
        self,
        exposure,
        limit,
    ):

        return self.engine.check(
            exposure,
            limit,
        )