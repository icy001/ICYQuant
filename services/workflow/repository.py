class WorkflowRepository:

    def __init__(self):
        self.workflows = {}

    def save(
        self,
        workflow
    ):
        self.workflows[
            workflow.workflow_id
        ] = workflow

    def get(
        self,
        workflow_id
    ):
        return self.workflows.get(
            workflow_id
        )
