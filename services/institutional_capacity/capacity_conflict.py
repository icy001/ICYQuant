"""
Capacity Conflict — Detects and resolves conflicting capacity demands.

When total strategy requests exceed market capacity, the system must
prioritize — it cannot execute everything.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .capacity_allocation import CapacityRequest


@dataclass
class CapacityConflict:
    """A capacity conflict between competing strategies."""

    conflict_id: str = field(default_factory=lambda: f"CC-{uuid.uuid4().hex[:8]}")
    asset: str = ""
    total_capacity: float = 0.0
    total_requested: float = 0.0
    shortfall: float = 0.0

    requests: List[CapacityRequest] = field(default_factory=list)
    resolved_allocations: Dict[str, float] = field(default_factory=dict)
    rejected: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "conflict_id": self.conflict_id,
            "asset": self.asset,
            "total_capacity": self.total_capacity,
            "total_requested": self.total_requested,
            "shortfall": self.shortfall,
            "resolved": self.resolved_allocations,
            "rejected": self.rejected,
        }


class CapacityConflictResolver:
    """Detects and resolves capacity conflicts."""

    def __init__(self):
        self._conflicts: List[CapacityConflict] = []

    def detect(
        self, asset: str, capacity: float,
        requests: List[CapacityRequest],
    ) -> Optional[CapacityConflict]:
        total_requested = sum(r.requested_amount for r in requests)
        if total_requested <= capacity:
            return None

        conflict = CapacityConflict(
            asset=asset, total_capacity=capacity,
            total_requested=total_requested,
            shortfall=total_requested - capacity,
            requests=requests,
        )
        self._conflicts.append(conflict)
        return conflict

    def resolve_by_priority(self, conflict: CapacityConflict) -> Dict[str, float]:
        """Resolve by strict priority order — highest score gets full request first."""
        remaining = conflict.total_capacity
        allocations: Dict[str, float] = {}

        sorted_req = sorted(conflict.requests, key=lambda r: r.priority_score, reverse=True)
        for r in sorted_req:
            if remaining <= 0:
                conflict.rejected.append(r.strategy_id)
                continue
            alloc = min(r.requested_amount, remaining)
            allocations[r.strategy_id] = alloc
            remaining -= alloc

        conflict.resolved_allocations = allocations
        return allocations

    def resolve_proportional(self, conflict: CapacityConflict) -> Dict[str, float]:
        """Resolve by proportional reduction."""
        scale = conflict.total_capacity / max(conflict.total_requested, 1.0)
        allocations = {r.strategy_id: r.requested_amount * scale for r in conflict.requests}
        conflict.resolved_allocations = allocations
        return allocations

    def history(self) -> List[CapacityConflict]:
        return list(self._conflicts)
