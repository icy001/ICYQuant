"""Execution Adapter — bridges the AI Platform to the Execution Engine / EMS.

The ExecutionAdapter translates AI agent execution plans into actual trade
executions through the Execution Management System. It handles order routing,
execution algorithm selection (TWAP, VWAP, etc.), and execution quality
analysis.

Capabilities:
    - Execution plan submission
    - Algorithm selection (TWAP, VWAP, Iceberg)
    - Execution monitoring
    - Slippage analysis
    - Execution quality reporting
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ExecutionAlgorithm(str, Enum):
    """Supported execution algorithms."""
    TWAP = "twap"
    VWAP = "vwap"
    ICEBERG = "iceberg"
    SMART_ROUTING = "smart_routing"
    DIRECT = "direct"


class ExecutionStatus(str, Enum):
    """Execution plan status."""
    CREATED = "created"
    SUBMITTED = "submitted"
    EXECUTING = "executing"
    COMPLETED = "completed"
    PARTIALLY_COMPLETED = "partially_completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ExecutionPlanRequest:
    """An execution plan from an AI agent."""
    plan_id: str = ""
    agent_id: str = ""
    orders: List[Dict[str, Any]] = field(default_factory=list)
    algorithm: ExecutionAlgorithm = ExecutionAlgorithm.TWAP
    duration_sec: float = 300.0
    max_slippage_pct: float = 0.10
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutionResult:
    """Result of an execution plan."""
    plan_id: str = ""
    execution_id: str = ""
    status: ExecutionStatus = ExecutionStatus.CREATED
    total_quantity: float = 0.0
    executed_quantity: float = 0.0
    avg_price: Optional[float] = None
    slippage_pct: float = 0.0
    cost_bps: float = 0.0
    error: Optional[str] = None
    started_at: Optional[float] = None
    completed_at: Optional[float] = None


class ExecutionAdapter:
    """Adapter for the ICYQuant Execution Engine / EMS.

    Translates AI agent execution plans into actual trade executions
    through the Execution Management System.

    Usage:
        ea = ExecutionAdapter()
        await ea.initialize()
        plan = ExecutionPlanRequest(agent_id="agent_1", orders=[...], algorithm=ExecutionAlgorithm.TWAP)
        result = await ea.submit_plan(plan)
    """

    def __init__(self) -> None:
        self._executions: Dict[str, ExecutionResult] = {}
        self._history: List[ExecutionResult] = []
        self._max_history: int = 5000
        self._total_plans: int = 0
        self._initialized: bool = False
        logger.info("ExecutionAdapter created")

    async def initialize(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        logger.info("ExecutionAdapter initialized")

    async def shutdown(self) -> None:
        self._executions.clear()
        self._history.clear()
        self._initialized = False
        logger.info("ExecutionAdapter shutdown complete")

    async def submit_plan(self, plan: ExecutionPlanRequest) -> ExecutionResult:
        """Submit an execution plan to the EMS.

        The EMS routes orders using the specified algorithm and monitors
        execution quality.
        """
        self._total_plans += 1
        execution_id = f"exec_{self._total_plans}"

        # TODO: Actual integration with Execution Engine / EMS
        result = ExecutionResult(
            plan_id=plan.plan_id,
            execution_id=execution_id,
            status=ExecutionStatus.SUBMITTED,
            total_quantity=sum(o.get("quantity", 0) for o in plan.orders),
            started_at=time.monotonic(),
        )

        self._executions[execution_id] = result
        logger.info("ExecutionAdapter: submitted plan %s (%s, %d orders) by agent %s", execution_id, plan.algorithm.value, len(plan.orders), plan.agent_id)
        return result

    async def cancel_execution(self, execution_id: str) -> bool:
        """Cancel an active execution."""
        execution = self._executions.get(execution_id)
        if execution and execution.status in (ExecutionStatus.SUBMITTED, ExecutionStatus.EXECUTING):
            execution.status = ExecutionStatus.CANCELLED
            self._history.append(execution)
            del self._executions[execution_id]
            logger.info("ExecutionAdapter: cancelled execution %s", execution_id)
            return True
        return False

    async def get_status(self, execution_id: str) -> Optional[ExecutionStatus]:
        """Get execution status."""
        execution = self._executions.get(execution_id)
        if execution:
            return execution.status
        for e in self._history:
            if e.execution_id == execution_id:
                return e.status
        return None

    async def get_agent_executions(self, agent_id: str, limit: int = 50) -> List[ExecutionResult]:
        """Get recent executions for an agent."""
        # Filter from history by plan_id prefix match
        return [e for e in self._history if e.plan_id.startswith(agent_id)][:limit]

    def get_summary(self) -> Dict[str, Any]:
        return {
            "initialized": self._initialized,
            "total_plans": self._total_plans,
            "active_executions": len(self._executions),
            "completed_executions": len(self._history),
        }
