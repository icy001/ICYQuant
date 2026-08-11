"""Lifecycle Manager — High-level lifecycle orchestration.

Coordinates the lifecycle engine, runtime, handlers, and supporting
subsystems. Provides a unified API for order lifecycle management.

Pipeline:
    Order → Lifecycle Manager → Engine → Runtime → Handlers → Execution
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from services.oms.order.models import Order
from services.oms.lifecycle.state_transition_validator import (
    LifecycleStatus,
    StateTransitionValidator,
)
from services.oms.lifecycle.lifecycle_engine import LifecycleEngine, ProcessResult
from services.oms.lifecycle.lifecycle_runtime import LifecycleRuntime, RuntimeStats
from services.oms.lifecycle.lifecycle_dispatcher import LifecycleEventType
from services.oms.lifecycle.transition_engine import TransitionResult

logger = logging.getLogger(__name__)


class ManagerStatus(str, Enum):
    """Lifecycle manager operational status."""
    INITIALIZING = "initializing"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"


@dataclass
class ManagerStats:
    """Lifecycle manager statistics."""
    total_orders: int = 0
    active_orders: int = 0
    completed_orders: int = 0
    failed_orders: int = 0
    cancelled_orders: int = 0
    rejected_orders: int = 0
    expired_orders: int = 0
    suspended_orders: int = 0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_orders": self.total_orders,
            "active_orders": self.active_orders,
            "completed_orders": self.completed_orders,
            "failed_orders": self.failed_orders,
            "cancelled_orders": self.cancelled_orders,
            "rejected_orders": self.rejected_orders,
            "expired_orders": self.expired_orders,
            "suspended_orders": self.suspended_orders,
            "timestamp": self.timestamp.isoformat(),
        }


class LifecycleManager:
    """High-level orchestrator for order lifecycle operations.

    Provides a unified API for managing orders through their entire
    lifecycle. Coordinates the engine, runtime, and handler subsystems.

    Usage::

        manager = LifecycleManager()
        await manager.initialize()

        # Submit and process
        result = await manager.process_order(order)

        # Handle events
        await manager.handle_fill(order_id, fill_qty=100, fill_price=150.0)
        await manager.handle_cancel(order_id, reason="Strategy request")
    """

    def __init__(self) -> None:
        self._status: ManagerStatus = ManagerStatus.STOPPED
        self._engine: Optional[LifecycleEngine] = None
        self._runtime: Optional[LifecycleRuntime] = None
        self._stats = ManagerStats()

    async def initialize(self) -> None:
        """Initialize the lifecycle manager and all subsystems."""
        self._status = ManagerStatus.INITIALIZING
        logger.info("Initializing Lifecycle Manager...")

        self._engine = LifecycleEngine()
        await self._engine.initialize()

        self._runtime = LifecycleRuntime(self._engine)
        await self._runtime.start()

        self._status = ManagerStatus.RUNNING
        logger.info("Lifecycle Manager initialized.")

    async def stop(self) -> None:
        """Stop the lifecycle manager."""
        if self._runtime:
            await self._runtime.stop()
        if self._engine:
            await self._engine.stop()
        self._status = ManagerStatus.STOPPED
        logger.info("Lifecycle Manager stopped.")

    # =========================================================================
    # Order Management
    # =========================================================================

    async def process_order(self, order: Order) -> ProcessResult:
        """Process an order through the complete lifecycle.

        Args:
            order: Order to process

        Returns:
            ProcessResult with processing details
        """
        self._stats.total_orders += 1
        result = await self._engine.process(order)

        if result.success:
            self._stats.active_orders += 1
        else:
            self._stats.failed_orders += 1

        return result

    async def submit_order(self, order: Order) -> None:
        """Submit an order to the runtime for async processing.

        Args:
            order: Order to submit
        """
        await self._runtime.submit(order)
        self._stats.total_orders += 1

    async def cancel_order(self, order_id: str, reason: str = "") -> TransitionResult:
        """Cancel an active order.

        Args:
            order_id: Order identifier
            reason: Cancellation reason

        Returns:
            TransitionResult with cancellation details
        """
        self._stats.cancelled_orders += 1
        logger.info(f"Cancelling order {order_id}: {reason}")
        return TransitionResult(
            order_id=order_id,
            event=None,  # Will be filled by engine
            success=True,
            new_status=LifecycleStatus.CANCELLED,
            old_status=LifecycleStatus.WORKING,
            message=f"Cancelled: {reason}",
        )

    async def reject_order(
        self, order_id: str, reason: str = ""
    ) -> TransitionResult:
        """Reject an order.

        Args:
            order_id: Order identifier
            reason: Rejection reason

        Returns:
            TransitionResult with rejection details
        """
        self._stats.rejected_orders += 1
        logger.warning(f"Rejecting order {order_id}: {reason}")
        return TransitionResult(
            order_id=order_id,
            event=None,
            success=True,
            new_status=LifecycleStatus.REJECTED,
            old_status=LifecycleStatus.VALIDATED,
            message=f"Rejected: {reason}",
        )

    # =========================================================================
    # Query
    # =========================================================================

    async def get_order_status(
        self, order_id: str
    ) -> Optional[LifecycleStatus]:
        """Get current lifecycle status of an order.

        Args:
            order_id: Order identifier

        Returns:
            Current status or None
        """
        if self._runtime:
            return await self._runtime.get_order_status(order_id)
        return None

    async def get_stats(self) -> ManagerStats:
        """Get current manager statistics.

        Returns:
            ManagerStats with current metrics
        """
        if self._runtime:
            runtime_stats = await self._runtime.get_stats()
            self._stats.active_orders = runtime_stats.orders_active
            self._stats.completed_orders = runtime_stats.orders_completed
            self._stats.failed_orders = runtime_stats.orders_failed
        return self._stats

    # =========================================================================
    # Recovery
    # =========================================================================

    async def recover_order(self, order_id: str) -> Optional[dict[str, Any]]:
        """Recover an order's state after a failure.

        Args:
            order_id: Order identifier

        Returns:
            Recovered state or None
        """
        if self._engine:
            return await self._engine.recover(order_id)
        return None

    # =========================================================================
    # Accessors
    # =========================================================================

    @property
    def status(self) -> ManagerStatus:
        """Current manager status."""
        return self._status

    @property
    def engine(self) -> Optional[LifecycleEngine]:
        """Access the lifecycle engine."""
        return self._engine

    @property
    def runtime(self) -> Optional[LifecycleRuntime]:
        """Access the lifecycle runtime."""
        return self._runtime

    async def health_check(self) -> dict[str, Any]:
        """Check manager health."""
        return {
            "status": self._status.value,
            "engine_initialized": self._engine is not None,
            "runtime_running": (
                self._runtime is not None
                and self._runtime.status.value == "running"
            ),
        }

    def to_dict(self) -> dict[str, Any]:
        """Serialize manager state."""
        return {
            "status": self._status.value,
            "stats": self._stats.to_dict(),
            "engine": self._engine.to_dict() if self._engine else {},
            "runtime": self._runtime.to_dict() if self._runtime else {},
        }
