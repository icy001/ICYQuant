"""
EMS Adapter — Connects Strategy Platform to the Execution Management System.

Provides interface for execution algorithm selection, smart order routing,
and execution quality tracking.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ExecutionAlgorithm(str, Enum):
    """Execution algorithm types."""
    TWAP = "twap"
    VWAP = "vwap"
    POV = "pov"  # Percentage of Volume
    IMPLEMENTATION_SHORTFALL = "implementation_shortfall"
    ICEBERG = "iceberg"
    SMART = "smart"
    DIRECT = "direct"


class ExecutionStatus(str, Enum):
    """Execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    PARTIALLY_COMPLETED = "partially_completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


@dataclass
class EMSExecutionRequest:
    """Request to execute an order via EMS."""
    strategy_id: str
    order_id: str
    instrument: str
    side: str  # buy/sell
    quantity: float
    algorithm: ExecutionAlgorithm = ExecutionAlgorithm.SMART
    urgency: int = 5  # 1-10, higher = more aggressive
    max_slippage_bps: float = 10.0
    time_horizon_seconds: float = 300.0  # Execution time window
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class EMSExecutionResult:
    """Result of an EMS execution."""
    execution_id: str
    order_id: str
    strategy_id: str
    instrument: str
    status: ExecutionStatus = ExecutionStatus.PENDING
    algorithm: ExecutionAlgorithm = ExecutionAlgorithm.SMART
    target_quantity: float = 0.0
    executed_quantity: float = 0.0
    average_price: float = 0.0
    slippage_bps: float = 0.0
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    fills: list[dict[str, Any]] = field(default_factory=list)
    error: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)


class EMSAdapter:
    """
    Adapter for the Execution Management System (EMS).

    Manages execution algorithm selection, smart order routing,
    and execution quality tracking for strategy orders.

    Usage::

        adapter = EMSAdapter()
        await adapter.initialize()
        result = await adapter.execute_order(EMSExecutionRequest(
            strategy_id="strat_001",
            order_id="oms_000001",
            instrument="AAPL",
            side="buy",
            quantity=1000,
            algorithm=ExecutionAlgorithm.VWAP,
        ))
    """

    def __init__(self) -> None:
        self._executions: dict[str, EMSExecutionResult] = {}
        self._counter: int = 0
        self._initialized: bool = False

    async def initialize(self) -> None:
        """Initialize the EMS adapter."""
        self._initialized = True
        logger.info("EMSAdapter initialized.")

    async def stop(self) -> None:
        """Stop the adapter."""
        self._initialized = False
        logger.info("EMSAdapter stopped.")

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    async def execute_order(self, request: EMSExecutionRequest) -> EMSExecutionResult:
        """Execute an order through the EMS."""
        self._counter += 1
        execution_id = f"ems_{self._counter:06d}"

        result = EMSExecutionResult(
            execution_id=execution_id,
            order_id=request.order_id,
            strategy_id=request.strategy_id,
            instrument=request.instrument,
            status=ExecutionStatus.RUNNING,
            algorithm=request.algorithm,
            target_quantity=request.quantity,
            metadata=request.metadata,
        )

        # Simulate execution completion
        result.status = ExecutionStatus.COMPLETED
        result.executed_quantity = request.quantity
        result.completed_at = datetime.now(timezone.utc)

        self._executions[execution_id] = result

        logger.info(f"Execution submitted: {execution_id} {request.algorithm.value} {request.quantity} {request.instrument}")
        return result

    async def get_execution(self, execution_id: str) -> Optional[EMSExecutionResult]:
        """Get an execution by ID."""
        return self._executions.get(execution_id)

    async def cancel_execution(self, execution_id: str) -> Optional[EMSExecutionResult]:
        """Cancel a running execution."""
        execution = self._executions.get(execution_id)
        if not execution:
            return None
        if execution.status in (ExecutionStatus.PENDING, ExecutionStatus.RUNNING):
            execution.status = ExecutionStatus.CANCELLED
            execution.completed_at = datetime.now(timezone.utc)
            logger.info(f"Execution cancelled: {execution_id}")
        return execution

    async def list_executions(
        self,
        strategy_id: Optional[str] = None,
        status: Optional[ExecutionStatus] = None,
        limit: int = 100,
    ) -> list[EMSExecutionResult]:
        """List executions with optional filters."""
        results = list(self._executions.values())
        if strategy_id:
            results = [e for e in results if e.strategy_id == strategy_id]
        if status:
            results = [e for e in results if e.status == status]
        return sorted(results, key=lambda e: e.started_at, reverse=True)[:limit]

    async def get_execution_quality(self, execution_id: str) -> Optional[dict[str, Any]]:
        """Get execution quality metrics."""
        execution = self._executions.get(execution_id)
        if not execution:
            return None
        return {
            "execution_id": execution_id,
            "algorithm": execution.algorithm.value,
            "slippage_bps": execution.slippage_bps,
            "fill_rate": execution.executed_quantity / execution.target_quantity if execution.target_quantity > 0 else 1.0,
            "status": execution.status.value,
        }

    async def health_check(self) -> dict[str, Any]:
        """Check adapter health."""
        return {
            "status": "healthy" if self._initialized else "not_initialized",
            "executions_tracked": len(self._executions),
            "active_executions": len([e for e in self._executions.values() if e.status == ExecutionStatus.RUNNING]),
        }
