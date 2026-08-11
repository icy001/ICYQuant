"""Lifecycle Runtime — Runtime execution and scheduling for order lifecycles.

Manages the runtime execution of order lifecycles, including scheduling,
queue management, and event-driven state progression.

Pipeline:
    Order → Lifecycle Engine → Transition Engine → Event Store → Snapshot → Execution

Key features:
- Async runtime loop for lifecycle processing
- Order queue management
- Event-driven state progression
- Health monitoring integration
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from services.oms.order.models import Order
from services.oms.lifecycle.state_transition_validator import LifecycleStatus
from services.oms.lifecycle.lifecycle_engine import LifecycleEngine, ProcessResult

logger = logging.getLogger(__name__)


class RuntimeStatus(str, Enum):
    """Lifecycle runtime operational status."""
    INITIALIZING = "initializing"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    STOPPED = "stopped"


@dataclass
class RuntimeStats:
    """Runtime execution statistics."""
    orders_processed: int = 0
    orders_active: int = 0
    orders_completed: int = 0
    orders_failed: int = 0
    queue_depth: int = 0
    avg_processing_time_ms: float = 0.0
    uptime_seconds: float = 0.0
    last_activity: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "orders_processed": self.orders_processed,
            "orders_active": self.orders_active,
            "orders_completed": self.orders_completed,
            "orders_failed": self.orders_failed,
            "queue_depth": self.queue_depth,
            "avg_processing_time_ms": self.avg_processing_time_ms,
            "uptime_seconds": self.uptime_seconds,
            "last_activity": self.last_activity.isoformat(),
        }


class LifecycleRuntime:
    """Runtime execution engine for order lifecycles.

    Manages the execution of orders through the lifecycle engine.
    Provides queue management, scheduling, and monitoring.

    Usage::

        runtime = LifecycleRuntime(lifecycle_engine)
        await runtime.start()
        await runtime.submit(order)
        stats = await runtime.get_stats()
    """

    def __init__(self, engine: LifecycleEngine) -> None:
        self._engine = engine
        self._status: RuntimeStatus = RuntimeStatus.STOPPED
        self._queue: asyncio.Queue[Order] = asyncio.Queue()
        self._active_orders: dict[str, Order] = {}
        self._completed_orders: dict[str, ProcessResult] = {}
        self._stats = RuntimeStats()
        self._start_time: Optional[datetime] = None
        self._tasks: list[asyncio.Task[Any]] = []

    async def start(self) -> None:
        """Start the lifecycle runtime."""
        if self._status == RuntimeStatus.RUNNING:
            return

        self._status = RuntimeStatus.INITIALIZING
        logger.info("Starting Lifecycle Runtime...")

        await self._engine.initialize()
        self._start_time = datetime.now(timezone.utc)
        self._status = RuntimeStatus.RUNNING

        # Start processing loop
        task = asyncio.create_task(self._process_loop())
        self._tasks.append(task)

        logger.info("Lifecycle Runtime started.")

    async def stop(self) -> None:
        """Stop the lifecycle runtime gracefully."""
        self._status = RuntimeStatus.STOPPING
        logger.info("Stopping Lifecycle Runtime...")

        for task in self._tasks:
            task.cancel()
        self._tasks.clear()

        await self._engine.stop()
        self._status = RuntimeStatus.STOPPED
        logger.info("Lifecycle Runtime stopped.")

    async def submit(self, order: Order) -> None:
        """Submit an order to the runtime for processing.

        Args:
            order: Order to process
        """
        await self._queue.put(order)
        self._active_orders[order.order_id] = order
        self._stats.orders_active = len(self._active_orders)
        self._stats.queue_depth = self._queue.qsize()

        logger.info(f"Order {order.order_id} queued for lifecycle processing")

    async def submit_batch(self, orders: list[Order]) -> None:
        """Submit multiple orders for processing.

        Args:
            orders: Orders to process
        """
        for order in orders:
            await self.submit(order)

    async def get_order_status(self, order_id: str) -> Optional[LifecycleStatus]:
        """Get the current lifecycle status of an order.

        Args:
            order_id: Order identifier

        Returns:
            Current lifecycle status or None
        """
        order = self._active_orders.get(order_id)
        if order:
            return LifecycleStatus(order.status.value)

        result = self._completed_orders.get(order_id)
        if result:
            return result.final_status

        return None

    async def get_stats(self) -> RuntimeStats:
        """Get current runtime statistics.

        Returns:
            RuntimeStats with current metrics
        """
        self._stats.queue_depth = self._queue.qsize()
        self._stats.orders_active = len(self._active_orders)
        if self._start_time:
            self._stats.uptime_seconds = (
                datetime.now(timezone.utc) - self._start_time
            ).total_seconds()
        return self._stats

    async def _process_loop(self) -> None:
        """Main processing loop — consumes orders from queue."""
        logger.info("Lifecycle Runtime processing loop started.")

        while self._status == RuntimeStatus.RUNNING:
            try:
                order = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break

            try:
                result = await self._engine.process(order)

                if result.success:
                    self._stats.orders_completed += 1
                else:
                    self._stats.orders_failed += 1

                self._completed_orders[order.order_id] = result
                self._active_orders.pop(order.order_id, None)

                self._stats.orders_processed += 1
                self._stats.last_activity = datetime.now(timezone.utc)
                self._stats.queue_depth = self._queue.qsize()

                logger.debug(
                    f"Order {order.order_id} processed: "
                    f"success={result.success}, "
                    f"duration={result.duration_ms:.1f}ms"
                )

            except Exception:
                logger.exception(
                    f"Error processing order {order.order_id} in runtime loop"
                )
                self._stats.orders_failed += 1

            finally:
                self._queue.task_done()

        logger.info("Lifecycle Runtime processing loop stopped.")

    @property
    def status(self) -> RuntimeStatus:
        """Current runtime status."""
        return self._status

    @property
    def engine(self) -> LifecycleEngine:
        """Access the lifecycle engine."""
        return self._engine

    def to_dict(self) -> dict[str, Any]:
        """Serialize runtime state."""
        return {
            "status": self._status.value,
            "stats": self._stats.to_dict(),
            "queue_depth": self._queue.qsize(),
            "active_orders": len(self._active_orders),
            "engine": self._engine.to_dict(),
        }
