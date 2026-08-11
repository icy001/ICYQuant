"""Workflow Adapter — bridges the AI Platform to the ICYQuant Workflow Engine.

The WorkflowAdapter translates AI agent plans into executable workflow DAGs,
submits them to the Workflow Engine, monitors execution, and returns results
to the AI Platform.

Capabilities:
    - Plan-to-workflow translation
    - Workflow submission and monitoring
    - Status polling and event subscription
    - Result aggregation and normalization
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class WorkflowStatus(str, Enum):
    """Workflow execution status."""
    SUBMITTED = "submitted"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class WorkflowTask:
    """A task to be executed in the workflow engine."""
    task_id: str = ""
    task_type: str = ""
    params: Dict[str, Any] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)


@dataclass
class WorkflowResult:
    """Result from a workflow execution."""
    workflow_id: str = ""
    status: WorkflowStatus = WorkflowStatus.SUBMITTED
    outputs: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    duration_ms: float = 0.0


class WorkflowAdapter:
    """Adapter for the ICYQuant Workflow Engine.

    Translates AI agent plans into executable workflows and manages
    their lifecycle through the Workflow Engine.

    Usage:
        wa = WorkflowAdapter()
        await wa.initialize()
        result = await wa.submit_workflow(agent_id="agent_1", tasks=[WorkflowTask(...)])
    """

    def __init__(self) -> None:
        self._pending: Dict[str, WorkflowResult] = {}
        self._completed: List[WorkflowResult] = []
        self._total_submitted: int = 0
        self._total_completed: int = 0
        self._total_failed: int = 0
        self._initialized: bool = False
        logger.info("WorkflowAdapter created")

    async def initialize(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        logger.info("WorkflowAdapter initialized")

    async def shutdown(self) -> None:
        self._pending.clear()
        self._completed.clear()
        self._initialized = False
        logger.info("WorkflowAdapter shutdown complete")

    async def submit_workflow(self, agent_id: str, tasks: List[WorkflowTask], workflow_name: str = "") -> WorkflowResult:
        """Submit a workflow for execution.

        Args:
            agent_id: The AI agent requesting the workflow.
            tasks: Ordered list of tasks with dependencies.
            workflow_name: Human-readable name for the workflow.
        """
        self._total_submitted += 1
        workflow_id = f"wf_{self._total_submitted}"

        result = WorkflowResult(workflow_id=workflow_id)
        self._pending[workflow_id] = result

        logger.info("WorkflowAdapter: submitted workflow %s (%s, %d tasks) by agent %s", workflow_id, workflow_name, len(tasks), agent_id)

        # TODO: Actual integration with Workflow Engine
        result.status = WorkflowStatus.RUNNING
        return result

    async def get_status(self, workflow_id: str) -> Optional[WorkflowStatus]:
        """Get the current status of a workflow."""
        result = self._pending.get(workflow_id)
        if result:
            return result.status
        for r in self._completed:
            if r.workflow_id == workflow_id:
                return r.status
        return None

    async def get_result(self, workflow_id: str) -> Optional[WorkflowResult]:
        """Get the result of a workflow execution."""
        return self._pending.get(workflow_id)

    async def cancel_workflow(self, workflow_id: str) -> bool:
        """Cancel a running workflow."""
        result = self._pending.get(workflow_id)
        if result and result.status == WorkflowStatus.RUNNING:
            result.status = WorkflowStatus.CANCELLED
            self._completed.append(result)
            del self._pending[workflow_id]
            return True
        return False

    def get_summary(self) -> Dict[str, Any]:
        return {
            "initialized": self._initialized,
            "total_submitted": self._total_submitted,
            "total_completed": self._total_completed,
            "total_failed": self._total_failed,
            "pending": len(self._pending),
        }
