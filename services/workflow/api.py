"""Workflow API — REST API endpoints for workflow management.

Provides HTTP endpoints for:
* Workflow registration and discovery
* Workflow execution
* Execution status queries
* Health and metrics

Endpoint summary::

    POST   /workflow/register     Register a new workflow definition
    POST   /workflow/execute      Start a workflow execution
    GET    /workflow/{id}         Get workflow definition
    GET    /workflow/list         List all workflows
    DELETE /workflow/{id}         Delete a workflow
    GET    /workflow/executions   List executions
    GET    /workflow/execution/{id}  Get execution status
    POST   /workflow/execution/{id}/cancel  Cancel execution
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from .workflow_engine import WorkflowEngine
from .workflow_definition import WorkflowDefinition

logger = logging.getLogger(__name__)


@dataclass
class APIResponse:
    """Standard API response wrapper."""

    success: bool
    data: Any = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {"success": self.success}
        if self.data is not None:
            result["data"] = self.data
        if self.error:
            result["error"] = self.error
        if self.metadata:
            result["metadata"] = self.metadata
        return result


class WorkflowAPI:
    """REST API surface for the Workflow Engine.

    Wraps the :class:`WorkflowEngine` with request/response handling,
    validation, and error normalization.
    """

    def __init__(self, engine: WorkflowEngine) -> None:
        self._engine = engine

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    async def register_workflow(self, definition: WorkflowDefinition) -> APIResponse:
        """Register a workflow definition.

        POST /workflow/register
        """
        try:
            workflow_id = await self._engine.register(definition)
            return APIResponse(
                success=True,
                data={"workflow_id": workflow_id, "version": definition.version},
            )
        except Exception as exc:
            logger.error("Failed to register workflow: %s", exc)
            return APIResponse(success=False, error=str(exc))

    async def deregister_workflow(self, workflow_id: str) -> APIResponse:
        """Remove a workflow from the registry.

        DELETE /workflow/{id}
        """
        try:
            await self._engine.deregister(workflow_id)
            return APIResponse(success=True, data={"workflow_id": workflow_id})
        except Exception as exc:
            return APIResponse(success=False, error=str(exc))

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    async def execute_workflow(
        self,
        definition: WorkflowDefinition,
        *,
        inputs: Optional[Dict[str, Any]] = None,
        trace_id: Optional[str] = None,
    ) -> APIResponse:
        """Start a workflow execution.

        POST /workflow/execute
        """
        try:
            execution_id = await self._engine.execute(
                definition=definition,
                inputs=inputs,
                trace_id=trace_id,
            )
            return APIResponse(
                success=True,
                data={"execution_id": execution_id},
            )
        except Exception as exc:
            logger.error("Failed to execute workflow: %s", exc)
            return APIResponse(success=False, error=str(exc))

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    async def get_workflow(self, workflow_id: str) -> APIResponse:
        """Get a workflow definition by id.

        GET /workflow/{id}
        """
        try:
            definition = await self._engine.get_definition(workflow_id)
            if definition is None:
                return APIResponse(success=False, error=f"Workflow not found: {workflow_id}")
            return APIResponse(success=True, data=definition.to_dict())
        except Exception as exc:
            return APIResponse(success=False, error=str(exc))

    async def list_workflows(
        self,
        *,
        status: Optional[str] = None,
        tag: Optional[str] = None,
    ) -> APIResponse:
        """List all registered workflows.

        GET /workflow/list
        """
        try:
            definitions = await self._engine.list_definitions()
            data = [d.to_dict() for d in definitions]
            return APIResponse(
                success=True,
                data=data,
                metadata={"count": len(data)},
            )
        except Exception as exc:
            return APIResponse(success=False, error=str(exc))

    async def get_execution_status(self, execution_id: str) -> APIResponse:
        """Get the status of a workflow execution.

        GET /workflow/execution/{id}
        """
        try:
            status = await self._engine.get_execution_status(execution_id)
            if status is None:
                return APIResponse(success=False, error=f"Execution not found: {execution_id}")
            return APIResponse(success=True, data=status)
        except Exception as exc:
            return APIResponse(success=False, error=str(exc))

    async def cancel_execution(self, execution_id: str) -> APIResponse:
        """Cancel a running workflow execution.

        POST /workflow/execution/{id}/cancel
        """
        try:
            cancelled = await self._engine.cancel_execution(execution_id)
            return APIResponse(success=True, data={"cancelled": cancelled})
        except Exception as exc:
            return APIResponse(success=False, error=str(exc))

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    async def health(self) -> APIResponse:
        """Return the health status of the workflow engine.

        GET /workflow/health
        """
        try:
            report = self._engine.health_report()
            return APIResponse(success=True, data=report)
        except Exception as exc:
            return APIResponse(success=False, error=str(exc))
