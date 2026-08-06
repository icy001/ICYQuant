"""Workflow Adapter — bridges the Scheduler with the Workflow Engine.

The :class:`WorkflowAdapter` translates scheduled job triggers into
workflow executions, manages workflow lifecycle, and reports results
back to the scheduler.

Pipeline::

    Scheduler Trigger
           │
    WorkflowAdapter
           │
    ┌──────┼──────┐
    Launch  Monitor  Recover
    └──────┼──────┘
      Workflow Engine
"""

from __future__ import annotations

import asyncio
import enum
import logging
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class WorkflowAdapterState(enum.Enum):
    """Workflow adapter lifecycle states."""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DEGRADED = "degraded"
    DISCONNECTING = "disconnecting"
    ERROR = "error"


class WorkflowAdapter:
    """Adapter that bridges scheduler triggers to workflow executions.

    Responsibilities:
    * Launch workflows from scheduled triggers
    * Monitor workflow execution progress
    * Recover workflows on scheduler failover
    * Manage workflow lifecycle (pause, resume, cancel)

    Usage::

        adapter = WorkflowAdapter(workflow_engine=engine)
        await adapter.connect()
        execution = await adapter.launch(trigger_context)
    """

    def __init__(self, workflow_engine: Any = None) -> None:
        self._engine = workflow_engine
        self._state = WorkflowAdapterState.DISCONNECTED
        self._lock = threading.Lock()
        self._active_workflows: Dict[str, Any] = {}
        self._launch_count: int = 0
        self._completion_count: int = 0
        self._failure_count: int = 0
        self._last_launch_at: Optional[datetime] = None
        self._retry_policy: Dict[str, Any] = {"max_retries": 3, "backoff": "exponential"}

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def state(self) -> WorkflowAdapterState:
        return self._state

    @property
    def active_workflows(self) -> int:
        return len(self._active_workflows)

    @property
    def launch_count(self) -> int:
        return self._launch_count

    @property
    def completion_count(self) -> int:
        return self._completion_count

    @property
    def failure_count(self) -> int:
        return self._failure_count

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def connect(self) -> None:
        """Connect to the workflow engine."""
        self._set_state(WorkflowAdapterState.CONNECTING)
        try:
            if self._engine and hasattr(self._engine, "connect"):
                await self._engine.connect()
            self._set_state(WorkflowAdapterState.CONNECTED)
            logger.info("WorkflowAdapter: connected")
        except Exception as exc:
            self._set_state(WorkflowAdapterState.ERROR)
            logger.error("WorkflowAdapter: connection failed: %s", exc)
            raise

    async def disconnect(self) -> None:
        """Disconnect from the workflow engine."""
        self._set_state(WorkflowAdapterState.DISCONNECTING)
        try:
            if self._engine and hasattr(self._engine, "disconnect"):
                await self._engine.disconnect()
            self._set_state(WorkflowAdapterState.DISCONNECTED)
        except Exception as exc:
            logger.warning("WorkflowAdapter: disconnect error: %s", exc)

    async def synchronize(self) -> Dict[str, Any]:
        """Synchronize workflow state with the scheduler."""
        return {"active_workflows": len(self._active_workflows), "state": self._state.value}

    # ------------------------------------------------------------------
    # Workflow Operations
    # ------------------------------------------------------------------

    async def launch(self, trigger_context: Dict[str, Any]) -> Dict[str, Any]:
        """Launch a workflow from a scheduler trigger.

        Translates the trigger context into a workflow execution request
        and submits it to the workflow engine.
        """
        self._launch_count += 1
        self._last_launch_at = datetime.now(timezone.utc)

        workflow_id = trigger_context.get("workflow_id", "")
        execution_request = {
            "workflow_id": workflow_id,
            "trigger_type": trigger_context.get("trigger_type", "unknown"),
            "schedule_id": trigger_context.get("schedule_id", ""),
            "parameters": trigger_context.get("parameters", {}),
            "launched_at": self._last_launch_at.isoformat(),
        }

        result: Dict[str, Any] = {
            "workflow_id": workflow_id,
            "status": "pending",
            "launched_at": self._last_launch_at.isoformat(),
        }

        try:
            if self._engine and hasattr(self._engine, "launch"):
                execution = await self._engine.launch(**execution_request)
                result["execution_id"] = getattr(execution, "execution_id", "")
                result["status"] = "launched"
                self._active_workflows[workflow_id] = execution
                logger.info("WorkflowAdapter: launched workflow %s", workflow_id)
            else:
                result["status"] = "no_engine"
                result["execution_id"] = f"mock-{workflow_id}"
        except Exception as exc:
            result["status"] = "error"
            result["error"] = str(exc)
            self._failure_count += 1
            logger.error("WorkflowAdapter: launch failed for %s: %s", workflow_id, exc)

        return result

    async def monitor(self, workflow_id: str) -> Dict[str, Any]:
        """Monitor the status of a running workflow."""
        workflow = self._active_workflows.get(workflow_id)
        if not workflow:
            return {"workflow_id": workflow_id, "status": "not_found"}

        status = "running"
        if self._engine and hasattr(self._engine, "get_status"):
            status = await self._engine.get_status(workflow_id)

        return {"workflow_id": workflow_id, "status": status}

    async def recover(self, workflow_id: str) -> Dict[str, Any]:
        """Recover a workflow after scheduler failover."""
        logger.info("WorkflowAdapter: recovering workflow %s", workflow_id)
        if self._engine and hasattr(self._engine, "recover"):
            result = await self._engine.recover(workflow_id)
            self._active_workflows[workflow_id] = result
            return {"workflow_id": workflow_id, "status": "recovered"}
        return {"workflow_id": workflow_id, "status": "recovery_not_supported"}

    async def cancel(self, workflow_id: str) -> Dict[str, Any]:
        """Cancel a running workflow."""
        if self._engine and hasattr(self._engine, "cancel"):
            await self._engine.cancel(workflow_id)
        self._active_workflows.pop(workflow_id, None)
        return {"workflow_id": workflow_id, "status": "cancelled"}

    async def pause(self, workflow_id: str) -> Dict[str, Any]:
        """Pause a running workflow."""
        if self._engine and hasattr(self._engine, "pause"):
            await self._engine.pause(workflow_id)
        return {"workflow_id": workflow_id, "status": "paused"}

    async def resume(self, workflow_id: str) -> Dict[str, Any]:
        """Resume a paused workflow."""
        if self._engine and hasattr(self._engine, "resume"):
            await self._engine.resume(workflow_id)
        return {"workflow_id": workflow_id, "status": "resumed"}

    # ------------------------------------------------------------------
    # Lifecycle Management
    # ------------------------------------------------------------------

    async def on_workflow_completed(self, workflow_id: str, result: Dict[str, Any]) -> None:
        """Callback when a workflow completes."""
        self._active_workflows.pop(workflow_id, None)
        self._completion_count += 1
        logger.info("WorkflowAdapter: workflow %s completed", workflow_id)

    async def on_workflow_failed(self, workflow_id: str, error: str) -> None:
        """Callback when a workflow fails."""
        self._active_workflows.pop(workflow_id, None)
        self._failure_count += 1
        logger.error("WorkflowAdapter: workflow %s failed: %s", workflow_id, error)

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _set_state(self, state: WorkflowAdapterState) -> None:
        with self._lock:
            self._state = state
