"""
Workflow engine.
"""


class WorkflowEngine:

    def __init__(
        self,
        orchestrator,
        tracker,
    ):

        self.orchestrator = orchestrator

        self.tracker = tracker


    def run(
        self,
        workflow,
        context,
    ):

        result = self.orchestrator.execute(
            context
        )

        self.tracker.track(
            workflow.experiment_id,
            result,
        )

        return result