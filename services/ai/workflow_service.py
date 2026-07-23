"""
AI workflow service.
"""


class WorkflowService:

    def __init__(
        self,
        runtime,
        monitor,
    ):

        self.runtime = runtime

        self.monitor = monitor

    def run(
        self,
        workflow,
    ):

        self.monitor.record(
            "workflow_started"
        )

        result = self.runtime.execute(
            workflow
        )

        self.monitor.record(
            "workflow_finished"
        )

        return result