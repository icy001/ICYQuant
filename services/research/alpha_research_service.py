"""
Alpha research service.
"""


class AlphaResearchService:

    def __init__(
        self,
        pipeline,
    ):

        self.pipeline = pipeline

    def run(
        self,
        *args,
        **kwargs,
    ):

        return self.pipeline.execute(
            *args,
            **kwargs,
        )