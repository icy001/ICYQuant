"""
Leverage risk pipeline.
"""


class LeveragePipeline:

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