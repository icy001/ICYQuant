"""
Risk orchestrator.
"""


class RiskOrchestrator:

    def __init__(
        self,
        pipeline,
    ):

        self.pipeline = pipeline

    def evaluate(
        self,
        context,
    ):

        return self.pipeline.execute(
            context,
        )