"""Unified workflow engine — the top-level entry point for workflow orchestration.

The :class:`WorkflowEngine` is responsible for:

* Workflow registration and discovery
* Workflow execution (definition → runtime → completion)
* Runtime lifecycle management (init → ready → run → stop)
* Coordinating the Manager, Definition, Runtime, and Repository layers

Architecture::

    WorkflowEngine
          │
    WorkflowManager
          │
    ┌──────┼──────┐
    Definition  Runtime  Repository
    └──────┼──────┘
    WorkflowExecutor
"""

from __future__ import annotations

import asyncio
import logging
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional

from .workflow_manager import WorkflowManager
from .workflow_runtime import WorkflowRuntime
from .workflow_registry import WorkflowRegistry
from .workflow_definition import WorkflowDefinition as WfDef
from .workflow_context import WorkflowContext

logger = logging.getLogger(__name__)


class EngineState:
    """Engine lifecycle states."""

    UNINITIALIZED = "uninitialized"
    INITIALIZING = "initializing"
    READY = "ready"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


class WorkflowEngine:
    """Top-level entry point for the ICYQuant workflow orchestration system.

    The engine wires together the Manager, Registry, Runtime, and Executor
    layers and provides a single API surface for registering, executing, and
    managing workflows.

    Usage::

        engine = WorkflowEngine()
        await engine.start()
        execution_id = await engine.execute(workflow_definition, inputs={...})
        await engine.shutdown()
    """

    def __init__(self, *, name: str = "default") -> None:
        self._name = name
        self._state = EngineState.UNINITIALIZED
        self._lock = threading.RLock()
        self._started_at: Optional[datetime] = None

        # Sub-systems — initialised lazily during start()
        self._manager: Optional[WorkflowManager] = None
        self._runtime: Optional[WorkflowRuntime] = None
        self._registry: Optional[WorkflowRegistry] = None

        self._active_executions: Dict[str, WorkflowContext] = {}

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return self._name

    @property
    def state(self) -> str:
        with self._lock:
            return self._state

    @property
    def is_ready(self) -> bool:
        return self._state == EngineState.READY

    @property
    def active_execution_count(self) -> int:
        with self._lock:
            return len(self._active_executions)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Initialise the engine and all sub-systems."""
        with self._lock:
            if self._state == EngineState.READY:
                return
            self._state = EngineState.INITIALIZING
            self._started_at = datetime.utcnow()

        logger.info("WorkflowEngine(%s): starting …", self._name)

        self._registry = WorkflowRegistry()
        self._runtime = WorkflowRuntime()
        self._manager = WorkflowManager(
            registry=self._registry,
            runtime=self._runtime,
        )

        await self._runtime.start()
        await self._manager.start()

        with self._lock:
            self._state = EngineState.READY
        logger.info("WorkflowEngine(%s): ready", self._name)

    async def shutdown(self) -> None:
        """Gracefully shut down the engine, draining in-flight executions."""
        with self._lock:
            self._state = EngineState.STOPPING

        logger.info("WorkflowEngine(%s): shutting down …", self._name)

        if self._manager:
            await self._manager.shutdown()
        if self._runtime:
            await self._runtime.shutdown()

        self._active_executions.clear()

        with self._lock:
            self._state = EngineState.STOPPED
        logger.info("WorkflowEngine(%s): stopped", self._name)

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    async def register(self, definition: WfDef) -> str:
        """Register a workflow definition and return its id."""
        if not self._registry:
            raise RuntimeError("Engine not started")
        workflow_id = await self._registry.register(definition)
        logger.info("WorkflowEngine(%s): registered workflow %s", self._name, workflow_id)
        return workflow_id

    async def deregister(self, workflow_id: str) -> None:
        """Remove a workflow from the registry."""
        if not self._registry:
            raise RuntimeError("Engine not started")
        await self._registry.deregister(workflow_id)

    async def get_definition(self, workflow_id: str) -> Optional[WfDef]:
        """Retrieve a registered workflow definition."""
        if not self._registry:
            return None
        return await self._registry.get(workflow_id)

    async def list_definitions(self) -> List[WfDef]:
        """Return all registered workflow definitions."""
        if not self._registry:
            return []
        return await self._registry.list_all()

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    async def execute(
        self,
        definition: WfDef,
        *,
        inputs: Optional[Dict[str, Any]] = None,
        trace_id: Optional[str] = None,
    ) -> str:
        """Execute a workflow definition and return the execution id.

        Parameters
        ----------
        definition:
            The workflow definition to execute.
        inputs:
            Optional input variables for the execution.
        trace_id:
            Optional distributed tracing identifier.
        """
        if not self._manager:
            raise RuntimeError("Engine not started")

        execution_id = await self._manager.execute(
            definition=definition,
            inputs=inputs or {},
            trace_id=trace_id,
        )
        logger.info("WorkflowEngine(%s): execution %s started", self._name, execution_id)
        return execution_id

    async def get_execution_status(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """Return the status of a running or completed execution."""
        if not self._manager:
            return None
        return await self._manager.get_execution_status(execution_id)

    async def cancel_execution(self, execution_id: str) -> bool:
        """Request cancellation of a running execution."""
        if not self._manager:
            return False
        return await self._manager.cancel_execution(execution_id)

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def health_report(self) -> Dict[str, Any]:
        """Return a health-check report for the engine and sub-systems."""
        report: Dict[str, Any] = {
            "engine": self._state == EngineState.READY,
            "name": self._name,
            "state": self._state,
            "started_at": self._started_at.isoformat() if self._started_at else None,
            "active_executions": self.active_execution_count,
            "subsystems": {},
        }
        if self._runtime:
            report["subsystems"]["runtime"] = self._runtime.health_report()
        if self._registry:
            report["subsystems"]["registry"] = self._registry.health_report()
        if self._manager:
            report["subsystems"]["manager"] = self._manager.health_report()
        return report
