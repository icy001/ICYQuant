"""
Workflow service.
"""

from .orchestrator import WorkflowOrchestrator


class WorkflowService:
    def __init__(
        self,
        orchestrator,
    ):
        self.orchestrator = orchestrator

    async def run(
        self,
        workflow,
    ):
        return await self.orchestrator.execute(workflow)