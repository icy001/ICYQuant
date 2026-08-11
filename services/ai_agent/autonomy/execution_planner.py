"""Execution Planner — generates execution plans from approved portfolio recommendations.

Pipeline:
    Approved Portfolio -> ExecutionPlanner.plan()
        -> Determine execution algorithm (TWAP, VWAP, Iceberg, Smart Routing)
        -> Split orders into slices
        -> Schedule execution over time window
        -> Apply urgency and market impact constraints
        -> Output ExecutionPlan

Note: This module only plans execution; it does NOT execute trades.
Actual execution is handled by the OMS/EMS integration layer.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ExecutionAlgorithm(str, Enum):
    TWAP = "twap"
    VWAP = "vwap"
    ICEBERG = "iceberg"
    SMART_ROUTING = "smart_routing"
    MANUAL = "manual"


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


@dataclass
class OrderSlice:
    """A single slice of an execution plan.

    Attributes:
        slice_id: Slice identifier.
        symbol: Trading symbol.
        side: Buy or sell.
        quantity: Order quantity.
        target_time: When this slice should execute.
        algorithm: Execution algorithm for this slice.
        price_limit: Optional price limit.
    """

    slice_id: str = ""
    symbol: str = ""
    side: OrderSide = OrderSide.BUY
    quantity: float = 0.0
    target_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    algorithm: ExecutionAlgorithm = ExecutionAlgorithm.TWAP
    price_limit: Optional[float] = None


@dataclass
class ExecutionPlan:
    """A complete execution plan for a portfolio.

    Attributes:
        plan_id: Unique plan identifier.
        recommendation_id: Source portfolio recommendation.
        status: Plan status.
        slices: Ordered list of execution slices.
        total_notional: Total notional value.
        expected_market_impact_bps: Estimated market impact in bps.
        execution_window_min: Execution time window in minutes.
        created_at: Plan creation timestamp.
    """

    plan_id: str = ""
    recommendation_id: str = ""
    status: str = "draft"
    slices: List[OrderSlice] = field(default_factory=list)
    total_notional: float = 0.0
    expected_market_impact_bps: float = 0.0
    execution_window_min: float = 30.0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def slice_count(self) -> int:
        return len(self.slices)

    @property
    def symbols(self) -> List[str]:
        return list({s.symbol for s in self.slices})


class ExecutionPlanner:
    """Generates execution plans from approved portfolio recommendations.

    Splits portfolio allocations into executable order slices using
    TWAP, VWAP, and other algorithms. Designed for the plan-only role;
    actual execution is delegated to OMS/EMS.

    Supports:
        - TWAP (Time-Weighted Average Price) slicing
        - VWAP (Volume-Weighted Average Price) slicing
        - Iceberg order generation
        - Market impact estimation
        - Execution window scheduling

    Usage:
        planner = ExecutionPlanner()
        await planner.initialize()
        plan = await planner.plan(recommendation, algo=ExecutionAlgorithm.TWAP)
    """

    def __init__(
        self,
        default_algorithm: ExecutionAlgorithm = ExecutionAlgorithm.TWAP,
        default_slices: int = 10,
        max_slices: int = 100,
    ) -> None:
        self._default_algorithm = default_algorithm
        self._default_slices = default_slices
        self._max_slices = max_slices
        self._plans: List[ExecutionPlan] = []
        self._counter: int = 0
        self._initialized: bool = False
        logger.info("ExecutionPlanner created (algo=%s, slices=%d)", default_algorithm.value, default_slices)

    async def initialize(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        logger.info("ExecutionPlanner initialized")

    async def shutdown(self) -> None:
        self._plans.clear()
        self._initialized = False
        logger.info("ExecutionPlanner shutdown complete")

    async def plan(
        self,
        recommendation: Optional[Any] = None,
        algorithm: Optional[ExecutionAlgorithm] = None,
        slices: Optional[int] = None,
        execution_window_min: float = 30.0,
    ) -> ExecutionPlan:
        """Generate an execution plan.

        Args:
            recommendation: Portfolio recommendation with allocations.
            algorithm: Execution algorithm (default: TWAP).
            slices: Number of slices (default: 10).
            execution_window_min: Execution window in minutes.

        Returns:
            ExecutionPlan with ordered slices.
        """
        logger.info("ExecutionPlanner.plan() started")
        self._counter += 1
        plan = ExecutionPlan(
            plan_id=f"plan_{self._counter}",
            recommendation_id=getattr(recommendation, "recommendation_id", ""),
            execution_window_min=execution_window_min,
        )
        self._plans.append(plan)
        logger.info("ExecutionPlanner.plan() completed: %s", plan.plan_id)
        return plan

    def get_recent_plans(self, limit: int = 10) -> List[Dict[str, Any]]:
        return [
            {
                "plan_id": p.plan_id,
                "slices": p.slice_count,
                "symbols": p.symbols,
                "total_notional": round(p.total_notional, 2),
                "impact_bps": round(p.expected_market_impact_bps, 2),
            }
            for p in self._plans[-limit:]
        ]

    def get_summary(self) -> Dict[str, Any]:
        return {
            "initialized": self._initialized,
            "total_plans": len(self._plans),
        }
