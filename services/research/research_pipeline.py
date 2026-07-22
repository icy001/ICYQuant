"""
End-to-end research pipeline.
"""


class ResearchPipeline:

    def __init__(
        self,
        scheduler,
        executor,
    ):

        self.scheduler = scheduler

        self.executor = executor

    def execute(
        self,
        workflow,
        notebook,
    ):

        self.scheduler.schedule(
            workflow
        )

        result = self.executor.run(
            notebook
        )

        workflow.state = "COMPLETED"

        return {
            "workflow": workflow,
            "result": result,
        }