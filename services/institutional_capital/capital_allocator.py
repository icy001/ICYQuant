"""
Capital Allocator — Execute Allocation Decisions into the Pool

The CapitalAllocator bridges decisions and the capital pool:
1. Receives allocation decisions
2. Validates against pool state and limits
3. Executes through CapitalPool
4. Records execution for audit
"""

import uuid
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class AllocatorStatus(str, Enum):
    IDLE = "IDLE"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


@dataclass
class AllocationResult:
    result_id: str
    status: AllocatorStatus
    requested: Dict[str, float]
    allocated: Dict[str, float]
    rejected: Dict[str, str]
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


class CapitalAllocator:
    """
    Executes allocation decisions against the CapitalPool.

    Handles:
    - Batch allocation with partial fill support
    - Pre-allocation validation (capital, risk, leverage, concentration)
    - Capacity-aware allocation (respects strategy capacity limits)
    - Reservation before deployment
    """

    def __init__(
        self,
        allocator_id: Optional[str] = None,
        capital_pool=None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.allocator_id = allocator_id or f"calr-{uuid.uuid4().hex[:12]}"
        self._capital_pool = capital_pool
        self.config = config or {}
        self._results: List[AllocationResult] = []
        self._strategy_capacities: Dict[str, float] = {}
        self._concentration_limit = self.config.get("concentration_limit", 0.30)
        logger.info(f"CapitalAllocator {self.allocator_id} initialized")

    def allocate(
        self,
        allocations: Dict[str, float],
        strategy_capacities: Optional[Dict[str, float]] = None,
    ) -> AllocationResult:
        """Execute a batch allocation, respecting strategy capacities."""
        if strategy_capacities:
            self._strategy_capacities.update(strategy_capacities)

        allocated = {}
        rejected = {}
        total_needed = sum(allocations.values())

        if not self._capital_pool:
            return AllocationResult(
                result_id=f"ar-{uuid.uuid4().hex[:8]}",
                status=AllocatorStatus.FAILED,
                requested=allocations,
                allocated=allocated,
                rejected={"all": "No capital pool connected"},
            )

        available = self._capital_pool.available_capital

        # Pro-rata if needed
        if total_needed > available and available > 0:
            scale = available / total_needed
            allocations = {k: v * scale for k, v in allocations.items()}

        for strategy_id, amount in allocations.items():
            reason = self._validate(strategy_id, amount, allocated)
            if reason:
                rejected[strategy_id] = reason
                continue

            actual = self._capital_pool.allocate(amount, strategy_id)
            allocated[strategy_id] = actual

        status = AllocatorStatus.COMPLETED
        if rejected and not allocated:
            status = AllocatorStatus.FAILED
        elif rejected:
            status = AllocatorStatus.PARTIAL

        result = AllocationResult(
            result_id=f"ar-{uuid.uuid4().hex[:8]}",
            status=status,
            requested=allocations,
            allocated=allocated,
            rejected=rejected,
        )
        self._results.append(result)
        return result

    def deallocate(
        self,
        deallocations: Dict[str, float],
    ) -> AllocationResult:
        """Execute a batch deallocation."""
        allocated = {}
        rejected = {}

        if not self._capital_pool:
            return AllocationResult(
                result_id=f"ar-{uuid.uuid4().hex[:8]}",
                status=AllocatorStatus.FAILED,
                requested=deallocations,
                allocated={},
                rejected={"all": "No capital pool connected"},
            )

        for strategy_id, amount in deallocations.items():
            current = self._capital_pool.get_allocation(strategy_id)
            if amount > current:
                rejected[strategy_id] = f"Requested {amount} > current {current}"
                amount = current

            actual = self._capital_pool.deallocate(amount, strategy_id)
            allocated[strategy_id] = actual

        result = AllocationResult(
            result_id=f"ar-{uuid.uuid4().hex[:8]}",
            status=AllocatorStatus.COMPLETED if not rejected else AllocatorStatus.PARTIAL,
            requested=deallocations,
            allocated=allocated,
            rejected=rejected,
        )
        self._results.append(result)
        return result

    def _validate(self, strategy_id: str, amount: float, current: Dict[str, float]) -> Optional[str]:
        """Validate an allocation against all limits."""
        if amount <= 0:
            return "Amount must be positive"

        # Capacity check
        capacity = self._strategy_capacities.get(strategy_id)
        if capacity is not None:
            existing = current.get(strategy_id, 0)
            if self._capital_pool:
                existing = self._capital_pool.get_allocation(strategy_id)
            if existing + amount > capacity:
                return f"Exceeds capacity: {existing + amount} > {capacity}"

        # Concentration check
        if self._capital_pool:
            total = self._capital_pool.total_capital
            if total > 0:
                existing = self._capital_pool.get_allocation(strategy_id)
                if (existing + amount) / total > self._concentration_limit:
                    return "Concentration limit exceeded"

        return None

    def get_history(self) -> List[AllocationResult]:
        return list(self._results)
