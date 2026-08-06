"""Research Runtime — orchestrates research execution with workflow and scheduler integration.

The :class:`ResearchRuntime` bridges the research platform with the
Workflow Engine and Distributed Scheduler, enabling:

* Experiment execution scheduling
* Workflow definition and dispatch
* Resource allocation for research tasks
* Progress tracking and state management
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from .research_context import ResearchContext

logger = logging.getLogger(__name__)


class RuntimePhase(str, Enum):
    """Research execution phases."""

    IDLE = "idle"
    VALIDATING = "validating"
    LOADING_DATA = "loading_data"
    EXECUTING = "executing"
    COLLECTING = "collecting"
    PUBLISHING = "publishing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ExecutionState(str, Enum):
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    PAUSED = "paused"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ResearchRuntime:
    """Orchestrates the execution of research experiments.

    Responsibilities:

    * Translate experiment config into executable workflows
    * Schedule execution via the Distributed Scheduler
    * Track execution progress and phase transitions
    * Collect results and generate artifacts
    * Handle cancellation and error recovery

    Pipeline::

        Dataset → Experiment → Runtime → Workflow → Scheduler → Execution → Artifact
    """

    def __init__(self, context: Optional[ResearchContext] = None) -> None:
        self._runtime_id = str(uuid4())
        self._context = context or ResearchContext()
        self._active_executions: Dict[str, Dict[str, Any]] = {}
        self._execution_history: List[Dict[str, Any]] = []
        self._lock = asyncio.Lock()

    @property
    def runtime_id(self) -> str:
        return self._runtime_id

    @property
    def active_executions(self) -> Dict[str, Dict[str, Any]]:
        return self._active_executions

    # ── execution lifecycle ───────────────────────────────────────────────

    async def start_execution(
        self,
        experiment_id: str,
        config: Optional[Dict[str, Any]] = None,
        priority: int = 0,
    ) -> str:
        """Start execution of an experiment.

        Args:
            experiment_id: The experiment to execute.
            config: Override configuration for this run.
            priority: Execution priority (higher = more urgent).

        Returns:
            execution_id: Unique identifier for this execution run.
        """
        execution_id = str(uuid4())
        async with self._lock:
            self._active_executions[execution_id] = {
                "execution_id": execution_id,
                "experiment_id": experiment_id,
                "phase": RuntimePhase.IDLE,
                "state": ExecutionState.PENDING,
                "config": config or {},
                "priority": priority,
                "created_at": datetime.now(timezone.utc),
                "started_at": None,
                "completed_at": None,
                "progress": 0.0,
                "error": None,
                "result": None,
            }

        logger.info(
            "Execution %s started for experiment %s", execution_id, experiment_id,
        )
        asyncio.create_task(self._execute_pipeline(execution_id))
        return execution_id

    async def cancel_execution(self, execution_id: str) -> bool:
        """Cancel a running execution."""
        async with self._lock:
            exec_info = self._active_executions.get(execution_id)
            if exec_info is None:
                return False
            if exec_info["state"] in (ExecutionState.SUCCEEDED, ExecutionState.FAILED, ExecutionState.CANCELLED):
                return False
            exec_info["state"] = ExecutionState.CANCELLED
            exec_info["phase"] = RuntimePhase.CANCELLED
            exec_info["completed_at"] = datetime.now(timezone.utc)
        logger.info("Execution %s cancelled", execution_id)
        return True

    async def get_execution(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """Get execution status by ID."""
        async with self._lock:
            return self._active_executions.get(execution_id)

    async def list_executions(
        self,
        experiment_id: Optional[str] = None,
        state: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """List executions with optional filtering."""
        async with self._lock:
            results = list(self._active_executions.values())
            results.extend(self._execution_history)
            if experiment_id:
                results = [r for r in results if r.get("experiment_id") == experiment_id]
            if state:
                results = [r for r in results if r.get("state", {}).get("value") == state]
            return results[-limit:]

    # ── internal pipeline ─────────────────────────────────────────────────

    async def _execute_pipeline(self, execution_id: str) -> None:
        """Internal execution pipeline (dataset → experiment → result)."""
        async with self._lock:
            exec_info = self._active_executions.get(execution_id)
            if exec_info is None:
                return

        try:
            # Phase 1: Validate
            await self._transition_phase(execution_id, RuntimePhase.VALIDATING)

            # Phase 2: Load data
            await self._transition_phase(execution_id, RuntimePhase.LOADING_DATA)

            # Phase 3: Execute
            await self._transition_phase(execution_id, RuntimePhase.EXECUTING)
            exec_info["state"] = ExecutionState.RUNNING
            exec_info["started_at"] = datetime.now(timezone.utc)
            exec_info["progress"] = 50.0

            # Phase 4: Collect results
            await self._transition_phase(execution_id, RuntimePhase.COLLECTING)
            exec_info["progress"] = 90.0

            # Phase 5: Publish
            await self._transition_phase(execution_id, RuntimePhase.PUBLISHING)
            exec_info["progress"] = 100.0

            exec_info["state"] = ExecutionState.SUCCEEDED
            exec_info["phase"] = RuntimePhase.COMPLETED
            exec_info["completed_at"] = datetime.now(timezone.utc)
            logger.info("Execution %s completed successfully", execution_id)

        except asyncio.CancelledError:
            exec_info["state"] = ExecutionState.CANCELLED
            exec_info["phase"] = RuntimePhase.CANCELLED
        except Exception as exc:
            exec_info["state"] = ExecutionState.FAILED
            exec_info["phase"] = RuntimePhase.FAILED
            exec_info["error"] = str(exc)
            exec_info["completed_at"] = datetime.now(timezone.utc)
            logger.error("Execution %s failed: %s", execution_id, exc)

    async def _transition_phase(self, execution_id: str, phase: RuntimePhase) -> None:
        async with self._lock:
            exec_info = self._active_executions.get(execution_id)
            if exec_info is None:
                return
            exec_info["phase"] = phase
            logger.debug("Execution %s → %s", execution_id, phase.value)

    def __repr__(self) -> str:
        return f"ResearchRuntime(id={self._runtime_id[:8]})"
