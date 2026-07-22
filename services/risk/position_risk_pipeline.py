"""
Position risk pipeline.
"""


class PositionRiskPipeline:

    def __init__(
        self,
        service,
    ):

        self.service = service

    def process(
        self,
        *args,
        **kwargs,
    ):

        return self.service.check(
            *args,
            **kwargs,
        )