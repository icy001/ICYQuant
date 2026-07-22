"""
Research report service.
"""


class ReportService:

    def __init__(
        self,
        pipeline,
    ):

        self.pipeline = pipeline

    def generate(
        self,
        *args,
        **kwargs,
    ):

        return self.pipeline.generate(
            *args,
            **kwargs,
        )