"""
Workflow orchestrator.
"""


class WorkflowOrchestrator:
    async def execute(
        self,
        workflow,
    ):
        return {
            "workflow": workflow.workflow_id,
            "status": "COMPLETED",
        }