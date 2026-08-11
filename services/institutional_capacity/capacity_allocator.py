"""
Capacity Allocator — Distributes capacity among competing strategy requests.

Priority-weighted allocation: higher alpha/efficiency = more capacity.
If total requested exceeds available, proportional or priority-based reduction.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .capacity_allocation import CapacityRequest, CapacityAllocation


class CapacityAllocator:
    """Allocates finite market capacity to strategy requests."""

    def __init__(self):
        self._allocations: List[CapacityAllocation] = []

    def allocate(
        self, asset: str, total_capacity: float,
        requests: List[CapacityRequest],
    ) -> CapacityAllocation:
        """Allocate capacity to competing requests. Priority-weighted proportional."""
        result = CapacityAllocation(asset=asset, total_capacity=total_capacity)

        if not requests:
            return result

        result.total_requested = sum(r.requested_amount for r in requests)

        # If total requested fits, allocate fully
        if result.total_requested <= total_capacity:
            for r in requests:
                result.allocations[r.strategy_id] = r.requested_amount
            result.total_allocated = result.total_requested
            return result

        # Priority-weighted allocation
        total_priority = sum(max(r.priority_score, 0.01) for r in requests)
        if total_priority <= 0:
            # Equal reduction
            scale = total_capacity / result.total_requested
            for r in requests:
                result.allocations[r.strategy_id] = r.requested_amount * scale
        else:
            remaining = total_capacity
            sorted_req = sorted(requests, key=lambda r: r.priority_score, reverse=True)
            for i, r in enumerate(sorted_req):
                # Weighted share of remaining
                weight = r.priority_score / total_priority
                alloc = min(r.requested_amount, remaining * weight * 1.2)
                alloc = min(alloc, remaining)
                if i == len(sorted_req) - 1:
                    alloc = remaining  # Last gets whatever is left
                if alloc <= 0:
                    result.rejected.append(r.strategy_id)
                else:
                    result.allocations[r.strategy_id] = alloc
                    remaining -= alloc

        result.total_allocated = sum(result.allocations.values())
        if result.total_allocated < 0.01 * total_capacity:
            result.rejected.extend([r.strategy_id for r in requests if r.strategy_id not in result.allocations])

        self._allocations.append(result)
        return result

    def history(self) -> List[CapacityAllocation]:
        return list(self._allocations)
