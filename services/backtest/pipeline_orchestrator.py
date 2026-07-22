"""
Pipeline orchestrator.
"""


class PipelineOrchestrator:

    def __init__(
        self,
        stages,
    ):

        self.stages = stages


    def execute(
        self,
        context,
    ):

        for stage in self.stages:

            context = stage.execute(
                context
            )

        return context