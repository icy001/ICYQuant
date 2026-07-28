from .state import WorkflowState


class WorkflowEngine:

    def __init__(
        self,
        executor
    ):
        self.executor = executor

    def run(
        self,
        workflow
    ):
        workflow_state = WorkflowState.RUNNING

        for task in workflow.tasks:
            self.executor.execute(
                task
            )

        workflow_state = WorkflowState.COMPLETED

        return workflow_state
