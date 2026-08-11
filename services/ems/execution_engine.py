"""Execution Engine — Core execution driver for the EMS.

The Execution Engine orchestrates the execution pipeline:
    1. Receive execution plan
    2. Initialize algorithm strategy
    3. Create and dispatch child orders on schedule
    4. Process fill events and update state
    5. Monitor and enforce execution limits

Architecture::

    ExecutionPlan → Engine.start() → Algorithm → Child Orders → Monitor → Complete

Usage::

    engine = ExecutionEngine()
    task = await engine.start(plan)
    await engine.pause(task)
    await engine.resume(task)
    await engine.terminate(task)
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from services.ems.algorithm.execution_strategy import ExecutionStrategy
from services.ems.algorithm.strategy_registry import StrategyRegistry
from services.ems.child_order import ChildOrder
from services.ems.execution_context import ExecutionContext
from services.ems.execution_dispatcher import ExecutionDispatcher
from services.ems.execution_event import ExecutionEvent, ExecutionEventType
from services.ems.execution_metadata import ExecutionMetadata
from services.ems.execution_monitor import ExecutionMonitor
from services.ems.execution_plan import ExecutionPlan
from services.ems.execution_runtime import ExecutionTask
from services.ems.execution_scheduler import ExecutionScheduler
from services.ems.execution_state import ExecutionStatus
from services.ems.metrics import EMSMetrics
from services.ems.telemetry import EMSTelemetry

logger = logging.getLogger(__name__)


class ExecutionEngine:
    """Core Execution Engine.

    Manages the lifecycle of an execution plan through the algorithm pipeline.
    Coordinates between the scheduler, algorithm strategy, dispatcher, and monitor.

    Attributes:
        scheduler: Execution scheduler for timing control
        dispatcher: Child order dispatcher to broker
        monitor: Execution quality monitor
        metrics: EMS Prometheus metrics
        telemetry: Distributed tracing support
        registry: Algorithm strategy registry
    """

    def __init__(
        self,
        scheduler: Optional[ExecutionScheduler] = None,
        dispatcher: Optional[ExecutionDispatcher] = None,
        monitor: Optional[ExecutionMonitor] = None,
        metrics: Optional[EMSMetrics] = None,
        telemetry: Optional[EMSTelemetry] = None,
    ) -> None:
        self.scheduler = scheduler or ExecutionScheduler()
        self.dispatcher = dispatcher or ExecutionDispatcher()
        self.monitor = monitor or ExecutionMonitor()
        self.metrics = metrics or EMSMetrics()
        self.telemetry = telemetry or EMSTelemetry()
        self.registry = StrategyRegistry()

        # Internal state
        self._strategies: dict[str, ExecutionStrategy] = {}
        self._plans: dict[str, ExecutionPlan] = {}
        self._tasks: dict[str, ExecutionTask] = {}
        self._child_orders: dict[str, list[ChildOrder]] = {}

    # ── Lifecycle API ──────────────────────────────────────────────

    async def start(self, plan: ExecutionPlan) -> ExecutionTask:
        """Start executing an execution plan.

        Initializes the algorithm strategy and begins the execution loop.

        Args:
            plan: Execution plan to execute

        Returns:
            ExecutionTask tracking the active execution
        """
        task_id = str(uuid.uuid4())
        parent_order_id = plan.context.parent_order.order_id

        with self.telemetry.trace_execution(task_id, plan.context.strategy):
            # Create task
            task = ExecutionTask(
                task_id=task_id,
                parent_order_id=parent_order_id,
                plan=plan,
                status=ExecutionStatus.PENDING,
            )

            # Initialize metadata
            metadata = ExecutionMetadata(
                execution_id=task_id,
                parent_order_id=parent_order_id,
                algorithm=plan.context.strategy,
                target_quantity=plan.context.total_quantity,
                remaining_quantity=plan.context.total_quantity,
                benchmark_price=plan.context.price_limit or 0.0,
            )
            metadata.start()

            # Resolve strategy
            strategy = self.registry.get(plan.context.strategy)
            if not strategy:
                raise ValueError(f"Unknown execution strategy: {plan.context.strategy}")

            # Initialize strategy
            await strategy.initialize(plan.context)

            # Store state
            self._strategies[task_id] = strategy
            self._plans[task_id] = plan
            self._tasks[task_id] = task
            self._child_orders[task_id] = []

            # Transition to submitting
            await self._transition(task, ExecutionStatus.SUBMITTING)

            # Start execution loop
            asyncio.ensure_future(self._execution_loop(task_id, metadata))

            logger.info(
                "Execution engine started: task=%s strategy=%s qty=%.0f",
                task_id,
                plan.context.strategy,
                plan.context.total_quantity,
            )
            return task

    async def pause(self, task: ExecutionTask) -> bool:
        """Pause an active execution.

        Stops the scheduler from producing new child orders.
        Existing child orders continue to execute.

        Args:
            task: Execution task to pause

        Returns:
            True if paused successfully
        """
        strategy = self._strategies.get(task.task_id)
        if not strategy:
            return False

        await strategy.pause()
        await self._transition(task, ExecutionStatus.PAUSED)
        self.metrics.record_execution_paused()
        return True

    async def resume(self, task: ExecutionTask) -> bool:
        """Resume a paused execution.

        Restarts the scheduler to produce new child orders.

        Args:
            task: Execution task to resume

        Returns:
            True if resumed successfully
        """
        strategy = self._strategies.get(task.task_id)
        if not strategy:
            return False

        await strategy.resume()
        await self._transition(task, ExecutionStatus.RESUMING)
        await self._transition(task, ExecutionStatus.ACTIVE)
        return True

    async def terminate(self, task: ExecutionTask) -> bool:
        """Terminate an execution.

        Cancels all active child orders and stops the algorithm.

        Args:
            task: Execution task to terminate

        Returns:
            True if terminated successfully
        """
        strategy = self._strategies.get(task.task_id)
        if not strategy:
            return False

        # Cancel all active child orders
        for child in self._child_orders.get(task.task_id, []):
            if not child.status.is_terminal:
                await self.dispatcher.cancel(child)

        await strategy.complete()
        await self._transition(task, ExecutionStatus.CANCELLED)

        self.metrics.record_execution_cancelled()
        logger.info("Execution terminated: task=%s", task.task_id)
        return True

    # ── Execution Loop ─────────────────────────────────────────────

    async def _execution_loop(self, task_id: str, metadata: ExecutionMetadata) -> None:
        """Main execution loop for an execution plan.

        Continuously generates child orders via the algorithm strategy
        and dispatches them. Runs until complete or error.

        Args:
            task_id: Execution task identifier
            metadata: Execution metadata for tracking
        """
        strategy = self._strategies.get(task_id)
        plan = self._plans.get(task_id)
        task = self._tasks.get(task_id)

        if not strategy or not plan or not task:
            logger.error("Missing state for task %s", task_id)
            return

        context = plan.context

        try:
            await self._transition(task, ExecutionStatus.ACTIVE)

            while not task.status.is_terminal:
                # Check if paused
                if task.status == ExecutionStatus.PAUSED:
                    await asyncio.sleep(0.1)
                    continue

                # Get next child order from algorithm
                child = await strategy.next_child_order(metadata)

                if child is None:
                    # Algorithm has no more child orders — check completion
                    if metadata.fill_pct >= 0.999 or metadata.remaining_quantity <= 0:
                        await self._transition(task, ExecutionStatus.COMPLETING)
                        await self._transition(task, ExecutionStatus.COMPLETED)
                        metadata.complete()
                        self.metrics.record_execution_completed()
                        logger.info("Execution completed: task=%s fill_pct=%.2f%%", task_id, metadata.fill_pct * 100)
                        break
                    else:
                        # Wait for next schedule tick
                        await asyncio.sleep(1.0)
                        continue

                # Dispatch child order
                self._child_orders[task_id].append(child)
                metadata.record_child_order(child.order_id)

                dispatched = await self.dispatcher.dispatch(child, context)
                if dispatched:
                    self.metrics.record_child_order_created(context.strategy)
                    with self.telemetry.trace_child_order(task_id, child.order_id):
                        # Monitor child order
                        asyncio.ensure_future(
                            self._monitor_child_order(task_id, child, metadata)
                        )

                # Update strategy with market context
                await strategy.update(metadata)

                # Schedule next iteration
                interval = context.slice_interval_seconds
                await asyncio.sleep(interval)

        except asyncio.CancelledError:
            logger.info("Execution loop cancelled: task=%s", task_id)
            await self._transition(task, ExecutionStatus.CANCELLED)
        except Exception as e:
            logger.exception("Execution loop error: task=%s error=%s", task_id, e)
            await self._transition(task, ExecutionStatus.ERROR)
            self.metrics.record_execution_error()

    async def _monitor_child_order(
        self, task_id: str, child: ChildOrder, metadata: ExecutionMetadata
    ) -> None:
        """Monitor a child order through its lifecycle.

        Processes fill events and updates cumulative execution metrics.

        Args:
            task_id: Parent execution task ID
            child: Child order to monitor
            metadata: Execution metadata to update
        """
        try:
            await self.monitor.monitor_child(child)

            if child.status == ChildOrder.FILLED:
                metadata.record_child_filled(child.order_id)
                metadata.apply_fill(
                    fill_qty=child.filled_quantity,
                    fill_price=child.average_price,
                    commission=child.commission or 0.0,
                )
                self.metrics.record_child_order_filled()
                self.metrics.record_fill_rate(metadata.fill_pct)

                # Notify strategy of fill
                strategy = self._strategies.get(task_id)
                if strategy:
                    await strategy.on_fill(child, metadata)

            elif child.status == ChildOrder.CANCELLED:
                metadata.record_child_cancelled(child.order_id)

            elif child.status == ChildOrder.REJECTED:
                metadata.record_child_cancelled(child.order_id)

        except Exception as e:
            logger.warning("Child order monitoring error: %s", e)

    # ── State Transition ───────────────────────────────────────────

    async def _transition(self, task: ExecutionTask, new_status: ExecutionStatus) -> None:
        """Transition a task to a new execution status.

        Validates the transition and emits an event.

        Args:
            task: Execution task
            new_status: Target status
        """
        from services.ems.execution_state import is_valid_transition

        if not is_valid_transition(task.status, new_status):
            logger.warning(
                "Invalid transition: task=%s from=%s to=%s",
                task.task_id,
                task.status,
                new_status,
            )
            return

        old_status = task.status
        task.status = new_status

        self.metrics.record_transition_latency(old_status.value, new_status.value)

    # ── Query API ──────────────────────────────────────────────────

    def get_strategy(self, task_id: str) -> Optional[ExecutionStrategy]:
        """Get the strategy for a task."""
        return self._strategies.get(task_id)

    def get_child_orders(self, task_id: str) -> list[ChildOrder]:
        """Get all child orders for a task."""
        return self._child_orders.get(task_id, [])

    def to_dict(self) -> dict[str, Any]:
        """Serialize engine state to dictionary."""
        return {
            "active_tasks": len(self._tasks),
            "strategies": list(self._strategies.keys()),
            "total_child_orders": sum(len(v) for v in self._child_orders.values()),
        }
