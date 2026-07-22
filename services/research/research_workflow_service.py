"""
Research workflow service.
"""


class ResearchWorkflowService:

    def __init__(
        self,
        pipeline,
    ):

        self.pipeline = pipeline

    def execute(
        self,
        workflow,
        notebook,
    ):

        return self.pipeline.execute(
            workflow,
            notebook,
        )