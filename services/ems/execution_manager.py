"""Execution Manager — High-level execution orchestration API.

Provides a simplified management interface for the EMS, handling
common orchestration patterns and coordination between components.

Usage::

    manager = ExecutionManager(ems=ems)
    task = await manager.submit_order(order, strategy="TWAP", duration=3600)
    status = await manager.get_execution_status(task.task_id)
    report = await manager.get_execution_report(task.task_id)
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from services.ems.execution_context import ExecutionContext
from services.ems.execution_management_system import ExecutionManagementSystem
from services.ems.execution_plan import ExecutionPlan
from services.ems.execution_report import ExecutionReport
from services.ems.execution_runtime import ExecutionTask
from services.ems.execution_state import ExecutionStatus
from services.ems.metrics import EMSMetrics

logger = logging.getLogger(__name__)


class ExecutionManager:
    """High-level execution manager.

    Coordinates between the EMS, execution plans, and monitoring.
    Provides a simplified API for submitting and managing executions.

    Attributes:
        ems: The Execution Management System
        metrics: EMS Prometheus metrics
    """

    def __init__(self, ems: Optional[ExecutionManagementSystem] = None) -> None:
        self.ems = ems or ExecutionManagementSystem()
        self.metrics = EMSMetrics()

    # ── Submission API ─────────────────────────────────────────────

    async def submit_order(
        self,
        order: Any,
        strategy: str = "TWAP",
        duration_seconds: float = 3600.0,
        max_slippage_bps: float = 10.0,
        **kwargs: Any,
    ) -> ExecutionTask:
        """Submit an OMS order for execution.

        Creates an execution context and submits to the EMS.

        Args:
            order: OMS Order to execute
            strategy: Algorithm strategy name
            duration_seconds: Execution duration
            max_slippage_bps: Maximum allowed slippage
            **kwargs: Additional strategy parameters

        Returns:
            ExecutionTask for tracking

        Raises:
            ValueError: If the order is not executable
        """
        context = ExecutionContext(
            parent_order=order,
            strategy=strategy,
            duration_seconds=duration_seconds,
            max_slippage_bps=max_slippage_bps,
            strategy_params=kwargs,
        )

        task = await self.ems.execute(context)
        logger.info(
            "Order submitted for execution: order=%s task=%s strategy=%s",
            order.order_id if hasattr(order, "order_id") else "unknown",
            task.task_id,
            strategy,
        )
        return task

    async def submit_plan(self, plan: ExecutionPlan) -> ExecutionTask:
        """Submit a pre-built execution plan.

        Args:
            plan: Execution plan to execute

        Returns:
            ExecutionTask for tracking
        """
        task = await self.ems.engine.start(plan)
        logger.info("Execution plan submitted: task=%s strategy=%s", task.task_id, plan.context.strategy)
        return task

    # ── Control API ────────────────────────────────────────────────

    async def pause_execution(self, task_id: str) -> bool:
        """Pause an active execution.

        Args:
            task_id: Execution task ID

        Returns:
            True if paused successfully
        """
        return await self.ems.pause(task_id)

    async def resume_execution(self, task_id: str) -> bool:
        """Resume a paused execution.

        Args:
            task_id: Execution task ID

        Returns:
            True if resumed successfully
        """
        return await self.ems.resume(task_id)

    async def cancel_execution(self, task_id: str) -> bool:
        """Cancel an active execution.

        Args:
            task_id: Execution task ID

        Returns:
            True if cancelled successfully
        """
        return await self.ems.terminate(task_id)

    # ── Query API ──────────────────────────────────────────────────

    async def get_execution_status(self, task_id: str) -> Optional[ExecutionStatus]:
        """Get current execution status.

        Args:
            task_id: Execution task ID

        Returns:
            ExecutionStatus or None
        """
        return await self.ems.get_status(task_id)

    async def get_execution_task(self, task_id: str) -> Optional[ExecutionTask]:
        """Get execution task details.

        Args:
            task_id: Execution task ID

        Returns:
            ExecutionTask or None
        """
        return await self.ems.get_task(task_id)

    async def get_active_executions(self) -> list[ExecutionTask]:
        """Get all active execution tasks.

        Returns:
            List of active ExecutionTask objects
        """
        return await self.ems.get_active_tasks()

    async def get_execution_report(self, task_id: str) -> Optional[ExecutionReport]:
        """Generate an execution report for a task.

        Args:
            task_id: Execution task ID

        Returns:
            ExecutionReport or None if task not found
        """
        task = await self.ems.get_task(task_id)
        if not task:
            return None

        from services.ems.execution_report import ExecutionReport

        engine = self.ems.engine
        child_orders = engine.get_child_orders(task_id)

        return ExecutionReport(
            task_id=task.task_id,
            parent_order_id=task.parent_order_id,
            status=task.status,
            child_orders=child_orders,
            duration_seconds=task.duration_seconds,
        )

    async def shutdown(self) -> None:
        """Gracefully shutdown all active executions."""
        tasks = await self.get_active_executions()
        for task in tasks:
            if task.status.is_cancellable:
                await self.ems.terminate(task.task_id)
        logger.info("Execution manager shut down: %d tasks terminated", len(tasks))

    def to_dict(self) -> dict[str, Any]:
        """Serialize manager state."""
        return {
            "ems": self.ems.to_dict(),
        }
