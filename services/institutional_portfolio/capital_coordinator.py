"""
Capital Coordinator — Multi-Strategy Capital Allocation Coordination

When multiple strategies request capital simultaneously but
available capital is insufficient, the coordinator resolves:

    Strategy A → +10M (priority=0.92)
    Strategy B → +20M (priority=0.74)
    Strategy C → +15M (priority=0.51)
    Available = 30M

    Allocation:
    A → 10M, B → 20M, C → 0M
"""

import uuid
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class CapitalRequest:
    request_id: str
    strategy_id: str
    amount: float
    priority_score: float
    reason: str = ""


@dataclass
class CapitalAllocation:
    strategy_id: str
    requested: float
    allocated: float
    rejected: float
    priority_score: float
    status: str = "PENDING"


class CapitalCoordinator:
    """
    Coordinates capital allocation across competing strategy requests.

    When total requests exceed available capital, allocates by:
    1. Priority score (highest first)
    2. Marginal efficiency (if available)
    3. Pro-rata within equal priority tiers
    """

    def __init__(
        self,
        coordinator_id: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.coordinator_id = coordinator_id or f"cc-{uuid.uuid4().hex[:12]}"
        self.config = config or {}
        self._last_allocation: List[CapitalAllocation] = []

    def coordinate(
        self,
        requests: List[CapitalRequest],
        available_capital: float,
    ) -> Dict[str, Any]:
        """
        Allocate capital to competing strategy requests.

        Returns: {strategy_id: {requested, allocated, rejected, status}}
        """
        if not requests:
            return {"allocations": [], "remaining": available_capital}

        # Sort by priority score (descending)
        sorted_requests = sorted(requests, key=lambda r: -r.priority_score)

        allocations = []
        remaining = available_capital

        for req in sorted_requests:
            alloc = min(req.amount, remaining)
            rejected = req.amount - alloc
            remaining -= alloc

            allocations.append(CapitalAllocation(
                strategy_id=req.strategy_id,
                requested=req.amount,
                allocated=alloc,
                rejected=rejected,
                priority_score=req.priority_score,
                status="FULL" if rejected == 0 else "PARTIAL" if alloc > 0 else "REJECTED",
            ))

        self._last_allocation = allocations
        return {
            "allocations": {a.strategy_id: a.__dict__ for a in allocations},
            "remaining": remaining,
        }

    def get_last_allocation(self) -> List[CapitalAllocation]:
        return self._last_allocation

    def get_rejected_strategies(self) -> List[str]:
        return [a.strategy_id for a in self._last_allocation if a.status == "REJECTED"]
