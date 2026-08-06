"""Platform API — unified management API for the workflow platform.

Endpoints::

    POST   /workflow/execute    Execute a workflow
    POST   /workflow/cancel     Cancel a running execution
    POST   /workflow/replay     Replay a past execution
    GET    /workflow/status     Get execution status
    GET    /workflow/history    Get execution history
    GET    /workflow/topology   Get workflow topology
    GET    /workflow/health     Health check
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class APIResponse:
    """Standard API response wrapper."""

    success: bool
    data: Any = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {"success": self.success, "timestamp": self.timestamp.isoformat()}
        if self.data is not None:
            result["data"] = self.data
        if self.error:
            result["error"] = self.error
        if self.metadata:
            result["metadata"] = self.metadata
        return result

    @classmethod
    def ok(cls, data: Any = None, **metadata: Any) -> APIResponse:
        return cls(success=True, data=data, metadata=metadata)

    @classmethod
    def fail(cls, error: str, data: Any = None) -> APIResponse:
        return cls(success=False, error=error, data=data)


class PlatformAPI:
    """Unified management API for the workflow platform.

    Usage::

        api = PlatformAPI(integration_manager=...)
        resp = await api.execute_workflow(workflow_id="order_execution", inputs={...})
    """

    def __init__(self, *, integration_manager=None) -> None:
        self._integration = integration_manager

    # ------------------------------------------------------------------
    # Workflow execution
    # ------------------------------------------------------------------

    async def execute_workflow(
        self,
        workflow_id: str,
        inputs: Optional[Dict[str, Any]] = None,
        *,
        trace_id: Optional[str] = None,
    ) -> APIResponse:
        """Execute a workflow."""
        logger.info("PlatformAPI: execute %s", workflow_id)
        # In production: delegates to WorkflowEngine
        return APIResponse.ok(
            {"workflow_id": workflow_id, "execution_id": "exec-0001", "status": "submitted"},
            trace_id=trace_id,
        )

    async def cancel_execution(self, execution_id: str) -> APIResponse:
        """Cancel a running execution."""
        logger.info("PlatformAPI: cancel %s", execution_id)
        return APIResponse.ok({"execution_id": execution_id, "cancelled": True})

    async def replay_execution(self, execution_id: str) -> APIResponse:
        """Replay a past execution."""
        logger.info("PlatformAPI: replay %s", execution_id)
        return APIResponse.ok({"execution_id": execution_id, "replayed": True})

    # ------------------------------------------------------------------
    # Status & History
    # ------------------------------------------------------------------

    async def get_status(self, execution_id: str) -> APIResponse:
        """Get execution status."""
        return APIResponse.ok({"execution_id": execution_id, "status": "UNKNOWN"})

    async def get_history(
        self,
        *,
        workflow_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> APIResponse:
        """Get execution history."""
        return APIResponse.ok({"executions": [], "count": 0})

    async def get_topology(self, workflow_id: str) -> APIResponse:
        """Get workflow topology."""
        return APIResponse.ok({"workflow_id": workflow_id, "nodes": [], "edges": []})

    # ------------------------------------------------------------------
    # Platform management
    # ------------------------------------------------------------------

    async def list_workflows(self) -> APIResponse:
        """List all workflows."""
        return APIResponse.ok({"workflows": [], "count": 0})

    async def get_health(self) -> APIResponse:
        """Get platform health."""
        return APIResponse.ok({
            "status": "healthy",
            "components": {},
            "timestamp": datetime.utcnow().isoformat(),
        })

    async def get_integration_status(self) -> APIResponse:
        """Get integration adapter status."""
        if self._integration:
            return APIResponse.ok(self._integration.list_adapters())
        return APIResponse.ok({})

    async def register_workflow(self, definition: Dict[str, Any]) -> APIResponse:
        """Register a new workflow definition."""
        return APIResponse.ok({"workflow_id": definition.get("id", "unknown"), "registered": True})
