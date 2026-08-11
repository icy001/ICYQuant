"""
Capital Allocator
=================
Manages capital distribution across strategies, assets, and positions.

Hierarchy:
    Capital Pool → Strategy Budget → Asset Budget → Position Budget
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class AllocationPolicy(str, Enum):
    """Capital allocation policies."""

    EQUAL_WEIGHT = "equal_weight"
    RISK_WEIGHTED = "risk_weighted"
    CONFIDENCE_WEIGHTED = "confidence_weighted"
    PERFORMANCE_WEIGHTED = "performance_weighted"
    CUSTOM = "custom"


@dataclass
class CapitalPool:
    """Represents a pool of capital for allocation."""

    pool_id: str = ""
    total_capital: float = 0.0
    allocated: float = 0.0
    available: float = 0.0
    reserved: float = 0.0
    currency: str = "USD"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def can_allocate(self, amount: float) -> bool:
        return self.available >= amount

    def reserve(self, amount: float) -> bool:
        if amount > self.available:
            return False
        self.reserved += amount
        self.available -= amount
        return True

    def release(self, amount: float) -> None:
        self.reserved = max(0.0, self.reserved - amount)
        self.available += amount

    def commit(self, amount: float) -> None:
        self.reserved = max(0.0, self.reserved - amount)
        self.allocated += amount


@dataclass
class AllocationRequest:
    """Request for capital allocation."""

    strategy_id: str = ""
    instrument: str = ""
    position_value: float = 0.0
    position_weight: float = 0.0
    confidence: float = 0.0
    priority: int = 5
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AllocationResult:
    """Result of a capital allocation."""

    strategy_id: str = ""
    instrument: str = ""
    requested: float = 0.0
    allocated: float = 0.0
    weight: float = 0.0
    status: str = "allocated"  # allocated, partial, rejected
    reason: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "instrument": self.instrument,
            "requested": self.requested,
            "allocated": self.allocated,
            "weight": self.weight,
            "status": self.status,
            "reason": self.reason,
            "metadata": self.metadata,
        }


class CapitalAllocator:
    """
    Capital Allocator.

    Distributes capital from pools to strategies, assets, and positions
    according to configurable allocation policies.

    Supports:
    - Multiple capital pools
    - Per-strategy budget caps
    - Priority-based allocation
    - Partial fills
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self._config = config or {}
        self._initialized = False

        # Capital pools
        self._pools: Dict[str, CapitalPool] = {}

        # Strategy budgets: strategy_id → max_capital
        self._strategy_budgets: Dict[str, float] = {}

        # Default policy
        self._policy = AllocationPolicy(
            self._config.get("policy", "confidence_weighted")
        )

        # Global caps
        self._max_per_strategy_pct = self._config.get("max_per_strategy_pct", 0.30)
        self._max_per_position_pct = self._config.get("max_per_position_pct", 0.10)

        # Metrics
        self._metrics: Dict[str, int] = {}

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        if self._initialized:
            return

        # Load strategy budgets from config
        budgets = self._config.get("strategy_budgets", {})
        for sid, budget in budgets.items():
            self._strategy_budgets[sid] = float(budget)

        # Create default pool if configured
        default_pool_config = self._config.get("default_pool", {})
        if default_pool_config:
            pool_id = default_pool_config.get("pool_id", "default")
            self._pools[pool_id] = CapitalPool(
                pool_id=pool_id,
                total_capital=default_pool_config.get("total_capital", 0.0),
                available=default_pool_config.get("total_capital", 0.0),
                currency=default_pool_config.get("currency", "USD"),
            )

        self._initialized = True
        logger.info(
            "CapitalAllocator initialized (policy=%s, pools=%d, budgets=%d)",
            self._policy.value,
            len(self._pools),
            len(self._strategy_budgets),
        )

    async def shutdown(self) -> None:
        self._pools.clear()
        self._strategy_budgets.clear()
        self._initialized = False
        logger.info("CapitalAllocator shut down")

    # ------------------------------------------------------------------
    # Pool Management
    # ------------------------------------------------------------------

    def create_pool(self, pool_id: str, total_capital: float, currency: str = "USD") -> CapitalPool:
        """Create a new capital pool."""
        pool = CapitalPool(
            pool_id=pool_id,
            total_capital=total_capital,
            available=total_capital,
            currency=currency,
        )
        self._pools[pool_id] = pool
        logger.info("Capital pool created: %s (%.2f %s)", pool_id, total_capital, currency)
        return pool

    def get_pool(self, pool_id: str) -> Optional[CapitalPool]:
        return self._pools.get(pool_id)

    def get_or_create_pool(self, pool_id: str, total_capital: float = 0.0) -> CapitalPool:
        """Get existing pool or create a new one."""
        if pool_id in self._pools:
            return self._pools[pool_id]
        return self.create_pool(pool_id, total_capital)

    def update_pool_capital(self, pool_id: str, total_capital: float) -> bool:
        """Update the total capital of a pool."""
        pool = self._pools.get(pool_id)
        if not pool:
            return False
        diff = total_capital - pool.total_capital
        pool.total_capital = total_capital
        pool.available = max(0.0, pool.available + diff)
        return True

    # ------------------------------------------------------------------
    # Budget Management
    # ------------------------------------------------------------------

    def set_strategy_budget(self, strategy_id: str, max_capital: float) -> None:
        """Set a capital budget for a specific strategy."""
        self._strategy_budgets[strategy_id] = max_capital
        logger.debug("Strategy budget set: %s = %.2f", strategy_id, max_capital)

    def get_strategy_budget(self, strategy_id: str) -> Optional[float]:
        return self._strategy_budgets.get(strategy_id)

    # ------------------------------------------------------------------
    # Allocation
    # ------------------------------------------------------------------

    def _resolve_requests(
        self,
        sized_positions: List[Dict[str, Any]],
    ) -> List[AllocationRequest]:
        """Convert sized position dicts to allocation requests."""
        requests = []
        for pos in sized_positions:
            req = AllocationRequest(
                strategy_id=pos.get("strategy_id", ""),
                instrument=pos.get("instrument", ""),
                position_value=pos.get("position_value", 0.0),
                position_weight=pos.get("position_weight", 0.0),
                confidence=pos.get("confidence", 0.0),
                priority=pos.get("priority", 5),
                metadata=pos.get("metadata", {}),
            )
            requests.append(req)
        return requests

    def _sort_by_policy(self, requests: List[AllocationRequest]) -> List[AllocationRequest]:
        """Sort requests according to allocation policy."""
        if self._policy == AllocationPolicy.EQUAL_WEIGHT:
            return requests
        elif self._policy == AllocationPolicy.RISK_WEIGHTED:
            return sorted(requests, key=lambda r: r.position_weight, reverse=True)
        elif self._policy == AllocationPolicy.CONFIDENCE_WEIGHTED:
            return sorted(requests, key=lambda r: r.confidence, reverse=True)
        elif self._policy == AllocationPolicy.PERFORMANCE_WEIGHTED:
            return sorted(requests, key=lambda r: (r.confidence * r.priority), reverse=True)
        else:
            return sorted(requests, key=lambda r: r.priority, reverse=True)

    async def allocate(
        self,
        sized_positions: List[Dict[str, Any]],
        portfolio_id: str,
        portfolio_state: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Allocate capital to sized positions.

        Args:
            sized_positions: Output from PositionSizingEngine.
            portfolio_id: Target portfolio.
            portfolio_state: Current portfolio state.

        Returns:
            List of allocated position dicts with capital assigned.
        """
        if not self._initialized:
            await self.initialize()

        requests = self._resolve_requests(sized_positions)
        if not requests:
            return []

        # Get or create pool for this portfolio
        pool_id = portfolio_id or "default"
        total_equity = (portfolio_state or {}).get("equity", 0.0)
        pool = self.get_or_create_pool(pool_id, total_equity if total_equity > 0 else 1000000.0)

        # Sort by policy
        sorted_requests = self._sort_by_policy(requests)

        results = []
        strategy_allocated: Dict[str, float] = {}

        for req in sorted_requests:
            requested = req.position_value

            # Check strategy budget
            strat_budget = self._strategy_budgets.get(req.strategy_id)
            if strat_budget is not None:
                current_strat_alloc = strategy_allocated.get(req.strategy_id, 0.0)
                remaining_strat = strat_budget - current_strat_alloc
                if remaining_strat <= 0:
                    results.append(AllocationResult(
                        strategy_id=req.strategy_id,
                        instrument=req.instrument,
                        requested=requested,
                        allocated=0.0,
                        weight=0.0,
                        status="rejected",
                        reason=f"Strategy budget exhausted ({strat_budget:.2f})",
                    ).to_dict())
                    continue
                requested = min(requested, remaining_strat)

            # Check pool availability
            if not pool.can_allocate(requested):
                # Partial fill
                available = pool.available
                if available <= 0:
                    results.append(AllocationResult(
                        strategy_id=req.strategy_id,
                        instrument=req.instrument,
                        requested=requested,
                        allocated=0.0,
                        weight=0.0,
                        status="rejected",
                        reason="Pool capital exhausted",
                    ).to_dict())
                    continue

                allocated = available
                status = "partial"
            else:
                allocated = requested
                status = "allocated"

            # Commit from pool
            pool.commit(allocated)

            # Track strategy allocation
            strategy_allocated[req.strategy_id] = (
                strategy_allocated.get(req.strategy_id, 0.0) + allocated
            )

            # Build result with original position data
            pos = sized_positions[len(results)] if len(results) < len(sized_positions) else {}
            result_dict = {
                **pos,
                "allocated_capital": allocated,
                "allocation_status": status,
                "allocation_weight": allocated / pool.total_capital if pool.total_capital > 0 else 0.0,
            }
            results.append(result_dict)

        self._metrics["allocated_total"] = self._metrics.get("allocated_total", 0) + len(results)
        self._metrics["capital_allocated"] = self._metrics.get("capital_allocated", 0) + sum(
            r.get("allocated_capital", 0) for r in results
        )

        logger.info(
            "Allocated %.2f to %d/%d positions (pool=%s, available=%.2f)",
            sum(r.get("allocated_capital", 0) for r in results),
            sum(1 for r in results if r.get("allocation_status") != "rejected"),
            len(results),
            pool_id,
            pool.available,
        )

        return results

    # ------------------------------------------------------------------
    # Observability
    # ------------------------------------------------------------------

    def get_metrics(self) -> Dict[str, Any]:
        return {
            **self._metrics,
            "pools": {pid: p.available for pid, p in self._pools.items()},
            "strategy_allocations": dict(self._strategy_budgets),
        }

    @property
    def is_initialized(self) -> bool:
        return self._initialized
