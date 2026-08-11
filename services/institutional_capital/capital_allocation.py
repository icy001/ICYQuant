"""
Capital Allocation — Granular Strategy-Level Capital Assignment

Models the allocation chain:
    Capital Pool → Strategy Allocation → Portfolio Allocation → Position Allocation

Tracks allocation lifecycle: PROPOSED → APPROVED → ACTIVE → DEPLOYED → RELEASED
"""

import uuid
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class AllocationState(str, Enum):
    PROPOSED = "PROPOSED"
    APPROVED = "APPROVED"
    ACTIVE = "ACTIVE"
    DEPLOYED = "DEPLOYED"
    REDUCING = "REDUCING"
    RELEASED = "RELEASED"
    REJECTED = "REJECTED"


class AllocationType(str, Enum):
    STRATEGY = "STRATEGY"
    PORTFOLIO = "PORTFOLIO"
    POSITION = "POSITION"
    RESEARCH = "RESEARCH"


@dataclass
class AllocationDetail:
    allocation_id: str
    allocation_type: AllocationType
    state: AllocationState = AllocationState.PROPOSED
    amount: float = 0.0
    strategy_id: Optional[str] = None
    portfolio_id: Optional[str] = None
    account_id: Optional[str] = None
    risk_budget: float = 0.0
    expected_return: float = 0.0
    expected_risk: float = 0.0
    created_at: datetime = field(default_factory=datetime.utcnow)
    approved_at: Optional[datetime] = None
    deployed_at: Optional[datetime] = None
    released_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class CapitalAllocation:
    """
    Manages the full lifecycle of capital allocations from proposal to release.

    Allocation chain:
        Capital Pool → Strategy → Portfolio → Position
    """

    def __init__(self, allocation_id: Optional[str] = None, config: Optional[Dict[str, Any]] = None):
        self.allocation_id = allocation_id or f"cal-{uuid.uuid4().hex[:12]}"
        self.config = config or {}
        self._allocations: Dict[str, AllocationDetail] = {}
        self._strategy_allocations: Dict[str, List[str]] = {}
        self._history: List[AllocationDetail] = []

    def propose(
        self,
        amount: float,
        strategy_id: str,
        allocation_type: AllocationType = AllocationType.STRATEGY,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AllocationDetail:
        detail = AllocationDetail(
            allocation_id=f"ald-{uuid.uuid4().hex[:8]}",
            allocation_type=allocation_type,
            state=AllocationState.PROPOSED,
            amount=amount,
            strategy_id=strategy_id,
            metadata=metadata or {},
        )
        self._allocations[detail.allocation_id] = detail
        self._strategy_allocations.setdefault(strategy_id, []).append(detail.allocation_id)
        logger.info(f"Allocation proposed: {detail.allocation_id} for {strategy_id}: {amount}")
        return detail

    def approve(self, alloc_id: str) -> AllocationDetail:
        detail = self._allocations[alloc_id]
        detail.state = AllocationState.APPROVED
        detail.approved_at = datetime.utcnow()
        return detail

    def activate(self, alloc_id: str) -> AllocationDetail:
        detail = self._allocations[alloc_id]
        detail.state = AllocationState.ACTIVE
        return detail

    def deploy(self, alloc_id: str) -> AllocationDetail:
        detail = self._allocations[alloc_id]
        detail.state = AllocationState.DEPLOYED
        detail.deployed_at = datetime.utcnow()
        self._history.append(detail)
        return detail

    def release(self, alloc_id: str) -> AllocationDetail:
        detail = self._allocations[alloc_id]
        detail.state = AllocationState.RELEASED
        detail.released_at = datetime.utcnow()
        return detail

    def reject(self, alloc_id: str, reason: str = "") -> AllocationDetail:
        detail = self._allocations[alloc_id]
        detail.state = AllocationState.REJECTED
        detail.metadata["reject_reason"] = reason
        return detail

    def get_strategy_total(self, strategy_id: str) -> float:
        ids = self._strategy_allocations.get(strategy_id, [])
        return sum(
            self._allocations[aid].amount
            for aid in ids
            if self._allocations[aid].state in (AllocationState.ACTIVE, AllocationState.DEPLOYED)
        )

    def get_total_allocated(self) -> float:
        return sum(
            d.amount for d in self._allocations.values()
            if d.state in (AllocationState.ACTIVE, AllocationState.DEPLOYED)
        )

    def get_summary(self) -> Dict[str, Any]:
        by_state = {}
        for d in self._allocations.values():
            by_state[d.state.value] = by_state.get(d.state.value, 0.0) + d.amount
        return {
            "allocation_id": self.allocation_id,
            "total_allocated": self.get_total_allocated(),
            "allocation_count": len(self._allocations),
            "by_state": by_state,
        }
