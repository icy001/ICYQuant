"""Execution Management System — Unified entry point for order execution.

The EMS is the central orchestrator for institutional order execution.
It receives orders from the OMS, creates execution plans, delegates to
algorithm strategies, and monitors execution quality.

Architecture::

    OMS → EMS.execute() → ExecutionEngine → Algorithm → Child Orders → Broker

Key responsibilities:
    - Receiving parent orders from OMS
    - Creating and managing execution plans
    - Delegating to algorithm strategies
    - Monitoring execution progress and quality
    - Pausing, resuming, and terminating executions
    - Producing execution reports

Usage::

    ems = ExecutionManagementSystem(engine=engine)
    task = await ems.execute(context)
    await ems.pause(task_id)
    await ems.resume(task_id)
    await ems.terminate(task_id)
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from services.ems.execution_context import ExecutionContext
from services.ems.execution_engine import ExecutionEngine
from services.ems.execution_event import ExecutionEvent, ExecutionEventType
from services.ems.execution_plan import ExecutionPlan
from services.ems.execution_runtime import ExecutionTask
from services.ems.execution_state import ExecutionStatus
from services.ems.metrics import EMSMetrics

logger = logging.getLogger(__name__)


class ExecutionManagementSystem:
    """Unified Execution Management System orchestrator.

    Manages the full lifecycle of execution tasks from submission to completion.
    Provides pause/resume/terminate control over active executions.

    Attributes:
        engine: Core execution engine
        metrics: EMS Prometheus metrics
        active_tasks: Map of active execution tasks
    """

    def __init__(self, engine: Optional[ExecutionEngine] = None) -> None:
        self.engine = engine or ExecutionEngine()
        self.metrics = EMSMetrics()
        self._active_tasks: dict[str, ExecutionTask] = {}
        self._task_statuses: dict[str, ExecutionStatus] = {}

    # ── Lifecycle API ──────────────────────────────────────────────

    async def execute(self, context: ExecutionContext) -> ExecutionTask:
        """Submit an order for execution.

        Creates an execution plan and starts the execution pipeline.
        The order will be decomposed into child orders by the algorithm.

        Args:
            context: Execution context with order, strategy, and parameters

        Returns:
            ExecutionTask representing the active execution

        Raises:
            ValueError: If the context validation fails
        """
        errors = context.validate()
        if errors:
            raise ValueError(f"Invalid execution context: {errors}")

        # Create execution plan
        plan = ExecutionPlan(context=context)

        # Start execution via engine
        task = await self.engine.start(plan)

        self._active_tasks[task.task_id] = task
        self._task_statuses[task.task_id] = ExecutionStatus.ACTIVE
        self.metrics.record_execution_task(context.strategy)
        self.metrics.record_active_tasks(len(self._active_tasks))

        logger.info(
            "Execution started: task=%s order=%s strategy=%s qty=%.0f",
            task.task_id,
            context.parent_order.order_id,
            context.strategy,
            context.total_quantity,
        )
        return task

    async def pause(self, task_id: str) -> bool:
        """Pause an active execution.

        The algorithm will stop producing new child orders, but existing
        child orders will continue to execute.

        Args:
            task_id: Execution task identifier

        Returns:
            True if paused successfully, False if task not found or not active
        """
        task = self._active_tasks.get(task_id)
        if not task:
            logger.warning("Cannot pause unknown task: %s", task_id)
            return False

        if not self._task_statuses.get(task_id, ExecutionStatus.ERROR).is_pausable:
            logger.warning("Cannot pause task %s in status %s", task_id, self._task_statuses.get(task_id))
            return False

        success = await self.engine.pause(task)
        if success:
            self._task_statuses[task_id] = ExecutionStatus.PAUSED
            logger.info("Execution paused: task=%s", task_id)
        return success

    async def resume(self, task_id: str) -> bool:
        """Resume a paused execution.

        The algorithm will resume producing child orders.

        Args:
            task_id: Execution task identifier

        Returns:
            True if resumed successfully, False if task not found or not paused
        """
        task = self._active_tasks.get(task_id)
        if not task:
            logger.warning("Cannot resume unknown task: %s", task_id)
            return False

        if self._task_statuses.get(task_id) != ExecutionStatus.PAUSED:
            logger.warning("Cannot resume task %s in status %s", task_id, self._task_statuses.get(task_id))
            return False

        success = await self.engine.resume(task)
        if success:
            self._task_statuses[task_id] = ExecutionStatus.ACTIVE
            logger.info("Execution resumed: task=%s", task_id)
        return success

    async def terminate(self, task_id: str) -> bool:
        """Terminate an execution.

        Cancels all active child orders and marks the execution as cancelled.
        Cannot be undone — creates a new execution if needed.

        Args:
            task_id: Execution task identifier

        Returns:
            True if terminated successfully, False if task not found
        """
        task = self._active_tasks.get(task_id)
        if not task:
            logger.warning("Cannot terminate unknown task: %s", task_id)
            return False

        success = await self.engine.terminate(task)
        if success:
            self._task_statuses[task_id] = ExecutionStatus.CANCELLED
            self._active_tasks.pop(task_id, None)
            self.metrics.record_active_tasks(len(self._active_tasks))
            logger.info("Execution terminated: task=%s", task_id)
        return success

    # ── Query API ──────────────────────────────────────────────────

    async def get_status(self, task_id: str) -> Optional[ExecutionStatus]:
        """Get current execution status for a task.

        Args:
            task_id: Execution task identifier

        Returns:
            Current execution status or None if task not found
        """
        return self._task_statuses.get(task_id)

    async def get_task(self, task_id: str) -> Optional[ExecutionTask]:
        """Get an execution task by ID.

        Args:
            task_id: Execution task identifier

        Returns:
            ExecutionTask or None if not found
        """
        return self._active_tasks.get(task_id)

    async def get_active_tasks(self) -> list[ExecutionTask]:
        """Get all currently active execution tasks.

        Returns:
            List of active execution tasks
        """
        return list(self._active_tasks.values())

    async def handle_event(self, event: ExecutionEvent) -> None:
        """Handle an execution event from the pipeline.

        Updates internal state based on execution events.

        Args:
            event: Execution event
        """
        task_id = event.parent_order_id

        if event.is_terminal:
            self._active_tasks.pop(task_id, None)
            self._task_statuses.pop(task_id, None)
            self.metrics.record_active_tasks(len(self._active_tasks))

            if event.event_type == ExecutionEventType.EXECUTION_COMPLETED:
                self.metrics.record_execution_completed()
            elif event.event_type == ExecutionEventType.EXECUTION_CANCELLED:
                self.metrics.record_execution_cancelled()
            elif event.event_type == ExecutionEventType.EXECUTION_REJECTED:
                self.metrics.record_execution_rejected()
            elif event.event_type == ExecutionEventType.EXECUTION_ERROR:
                self.metrics.record_execution_error()

    def to_dict(self) -> dict[str, Any]:
        """Serialize EMS state to dictionary."""
        return {
            "active_tasks_count": len(self._active_tasks),
            "task_statuses": {
                tid: status.value for tid, status in self._task_statuses.items()
            },
            "active_task_ids": list(self._active_tasks.keys()),
        }
