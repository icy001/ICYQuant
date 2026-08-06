"""Workflow Manager — coordinates definition, runtime, and execution layers.

The :class:`WorkflowManager` is the central coordinator. It delegates to:

* :class:`WorkflowRegistry` for definition storage and lookup
* :class:`WorkflowRuntime` for runtime instance lifecycle
* :class:`WorkflowExecutor` for actual execution of workflow instances
"""

from __future__ import annotations

import asyncio
import logging
import threading
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from .workflow_registry import WorkflowRegistry
from .workflow_runtime import WorkflowRuntime
from .workflow_definition import WorkflowDefinition as WfDef
from .workflow_context import WorkflowContext
from .workflow_executor import WorkflowExecutor

logger = logging.getLogger(__name__)


class ManagerState:
    UNINITIALIZED = "uninitialized"
    INITIALIZING = "initializing"
    READY = "ready"
    STOPPING = "stopping"
    STOPPED = "stopped"


class WorkflowManager:
    """Central coordinator for workflow lifecycle.

    The Manager sits between the Engine and the lower-level components,
    orchestrating registration → validation → execution → monitoring.
    """

    def __init__(
        self,
        *,
        registry: WorkflowRegistry,
        runtime: WorkflowRuntime,
        executor: Optional[WorkflowExecutor] = None,
    ) -> None:
        self._registry = registry
        self._runtime = runtime
        self._executor = executor or WorkflowExecutor(runtime=runtime)
        self._state = ManagerState.UNINITIALIZED
        self._lock = threading.RLock()
        self._executions: Dict[str, WorkflowContext] = {}
        self._execution_tasks: Dict[str, asyncio.Task] = {}
        self._started_at: Optional[datetime] = None

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def state(self) -> str:
        with self._lock:
            return self._state

    @property
    def active_executions(self) -> int:
        with self._lock:
            return len(self._executions)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        with self._lock:
            self._state = ManagerState.INITIALIZING
            self._started_at = datetime.utcnow()
        logger.info("WorkflowManager: starting …")
        await self._executor.start()
        with self._lock:
            self._state = ManagerState.READY
        logger.info("WorkflowManager: ready")

    async def shutdown(self) -> None:
        with self._lock:
            self._state = ManagerState.STOPPING
        logger.info("WorkflowManager: shutting down (draining %d executions) …", len(self._executions))
        # Cancel all in-flight executions
        for task in list(self._execution_tasks.values()):
            task.cancel()
        if self._execution_tasks:
            await asyncio.gather(*self._execution_tasks.values(), return_exceptions=True)
        await self._executor.shutdown()
        self._executions.clear()
        self._execution_tasks.clear()
        with self._lock:
            self._state = ManagerState.STOPPED
        logger.info("WorkflowManager: stopped")

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    async def execute(
        self,
        *,
        definition: WfDef,
        inputs: Dict[str, Any],
        trace_id: Optional[str] = None,
    ) -> str:
        """Start a new workflow execution and return the execution id."""
        execution_id = str(uuid.uuid4())
        context = WorkflowContext(
            workflow_id=definition.name,
            execution_id=execution_id,
            trace_id=trace_id,
        )
        context.update_variables(inputs)

        with self._lock:
            self._executions[execution_id] = context

        # Schedule the execution as a background task
        task = asyncio.ensure_future(
            self._executor.execute(definition=definition, context=context)
        )
        self._execution_tasks[execution_id] = task

        logger.info("WorkflowManager: execution %s scheduled", execution_id)
        return execution_id

    async def get_execution_status(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """Return the status of a tracked execution."""
        context = self._executions.get(execution_id)
        if context is None:
            return None
        return {
            "execution_id": execution_id,
            "workflow_id": context.workflow_id,
            "variables": context.get_variables(),
            "metadata": context.get_metadata("status", "unknown"),
        }

    async def cancel_execution(self, execution_id: str) -> bool:
        """Request cancellation of a running execution."""
        task = self._execution_tasks.get(execution_id)
        if task is None or task.done():
            return False
        task.cancel()
        return True

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def health_report(self) -> Dict[str, Any]:
        return {
            "state": self._state,
            "started_at": self._started_at.isoformat() if self._started_at else None,
            "active_executions": self.active_executions,
            "total_executions": len(self._execution_tasks),
        }
