"""
Workflow Adapter — Connects Strategy Platform to the Workflow Engine.

Provides interface for triggering and monitoring workflow executions
related to strategy deployment, evaluation, and promotion.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class WorkflowStatus(str, Enum):
    """Workflow execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"


@dataclass
class WorkflowTrigger:
    """Workflow trigger request."""
    workflow_name: str
    strategy_id: str
    params: dict[str, Any] = field(default_factory=dict)
    priority: int = 0
    timeout_seconds: float = 3600.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkflowExecution:
    """Workflow execution result."""
    execution_id: str
    workflow_name: str
    strategy_id: str
    status: WorkflowStatus = WorkflowStatus.PENDING
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    result: dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


class WorkflowAdapter:
    """
    Adapter for the Workflow Engine.

    Enables strategies to trigger workflow executions (deployment
    pipelines, evaluation runs, promotion processes) through a
    standardized interface.

    Usage::

        adapter = WorkflowAdapter()
        await adapter.initialize()
        execution = await adapter.trigger_workflow(WorkflowTrigger(
            workflow_name="strategy_deployment",
            strategy_id="strat_001",
            params={"version": "1.2.0"},
        ))
    """

    def __init__(self) -> None:
        self._executions: dict[str, WorkflowExecution] = {}
        self._counter: int = 0
        self._initialized: bool = False

    async def initialize(self) -> None:
        """Initialize the workflow adapter."""
        self._initialized = True
        logger.info("WorkflowAdapter initialized.")

    async def stop(self) -> None:
        """Stop the adapter."""
        self._initialized = False
        logger.info("WorkflowAdapter stopped.")

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    async def trigger_workflow(self, trigger: WorkflowTrigger) -> WorkflowExecution:
        """Trigger a workflow execution."""
        self._counter += 1
        execution_id = f"wf_{self._counter:06d}"

        execution = WorkflowExecution(
            execution_id=execution_id,
            workflow_name=trigger.workflow_name,
            strategy_id=trigger.strategy_id,
            status=WorkflowStatus.RUNNING,
        )
        self._executions[execution_id] = execution

        # Simulate workflow completion
        execution.status = WorkflowStatus.COMPLETED
        execution.completed_at = datetime.now(timezone.utc)
        execution.result = {"output": "completed", "steps": 3}

        logger.info(f"Workflow triggered: {trigger.workflow_name} ({execution_id})")
        return execution

    async def get_execution(self, execution_id: str) -> Optional[WorkflowExecution]:
        """Get workflow execution status."""
        return self._executions.get(execution_id)

    async def cancel_workflow(self, execution_id: str) -> bool:
        """Cancel a running workflow."""
        execution = self._executions.get(execution_id)
        if not execution or execution.status not in (WorkflowStatus.PENDING, WorkflowStatus.RUNNING):
            return False
        execution.status = WorkflowStatus.CANCELLED
        execution.completed_at = datetime.now(timezone.utc)
        logger.info(f"Workflow cancelled: {execution_id}")
        return True

    async def list_executions(
        self,
        strategy_id: Optional[str] = None,
        status: Optional[WorkflowStatus] = None,
        limit: int = 100,
    ) -> list[WorkflowExecution]:
        """List workflow executions with filters."""
        results = list(self._executions.values())
        if strategy_id:
            results = [e for e in results if e.strategy_id == strategy_id]
        if status:
            results = [e for e in results if e.status == status]
        return sorted(results, key=lambda e: e.started_at, reverse=True)[:limit]

    async def health_check(self) -> dict[str, Any]:
        """Check adapter health."""
        return {
            "status": "healthy" if self._initialized else "not_initialized",
            "executions_tracked": len(self._executions),
        }
