"""
Capacity Controller — Capacity-aware flow controller.

Sits between portfolio decisions and execution, enforcing capacity constraints:
    - Rejects orders exceeding capacity
    - Resizes based on participation limits
    - Throttles during stressed regimes
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .capacity_intelligence import CapacityIntelligence, CapacitySnapshot, CapacityState


class CapacityControllerAction(str):
    PROCEED = "proceed"
    RESIZE = "resize"
    SPLIT = "split"
    DEFER = "defer"
    REJECT = "reject"


@dataclass
class CapacityControlResult:
    """Result of capacity control check on an order/request."""

    result_id: str = field(default_factory=lambda: f"CCR-{uuid.uuid4().hex[:8]}")
    strategy_id: str = ""
    asset: str = ""
    requested: float = 0.0
    approved: float = 0.0
    action: str = CapacityControllerAction.PROCEED
    reason: str = ""
    snapshot: Optional[CapacitySnapshot] = None
    splits: List[float] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "result_id": self.result_id,
            "strategy_id": self.strategy_id,
            "asset": self.asset,
            "requested": self.requested,
            "approved": self.approved,
            "action": self.action,
            "reason": self.reason,
        }

    @property
    def resize_ratio(self) -> float:
        return self.approved / max(self.requested, 1.0)


class CapacityController:
    """Controls order flow based on capacity constraints."""

    def __init__(self, intelligence: Optional[CapacityIntelligence] = None):
        self._intelligence = intelligence or CapacityIntelligence()
        self._results: List[CapacityControlResult] = []
        self._throttle_enabled = False
        self._throttle_multiplier = 1.0

    def enable_throttle(self, multiplier: float = 0.5) -> None:
        self._throttle_enabled = True
        self._throttle_multiplier = multiplier

    def disable_throttle(self) -> None:
        self._throttle_enabled = False
        self._throttle_multiplier = 1.0

    def check(
        self,
        strategy_id: str,
        asset: str,
        requested: float,
        avg_daily_volume: float = 0.0,
        volatility: float = 0.0,
        spread_bps: float = 0.0,
    ) -> CapacityControlResult:
        """Check if an order can proceed given capacity constraints."""
        result = CapacityControlResult(
            strategy_id=strategy_id,
            asset=asset,
            requested=requested,
            approved=requested,
        )

        snapshot = self._intelligence.assess(
            strategy_id, asset, requested, avg_daily_volume, volatility, spread_bps,
        )
        result.snapshot = snapshot

        # Apply throttle
        if self._throttle_enabled:
            result.approved *= self._throttle_multiplier
            result.action = CapacityControllerAction.RESIZE
            result.reason = f"Throttle active: {self._throttle_multiplier:.0%}"

        # Capacity constraint
        if snapshot.state == CapacityState.RESIZED:
            result.approved = min(result.approved, snapshot.executable_capital)
            result.action = CapacityControllerAction.RESIZE
            result.reason = snapshot.binding_constraint or "capacity_limit"

        # Participation limit
        if avg_daily_volume > 0:
            max_participation = self._intelligence.context.max_participation_rate
            max_by_participation = avg_daily_volume * max_participation
            if result.approved > max_by_participation:
                result.approved = max_by_participation
                if result.action == CapacityControllerAction.PROCEED:
                    result.action = CapacityControllerAction.RESIZE
                result.reason = f"Participation limit {max_participation:.0%}"

        # Splitting logic for large orders
        if result.action == CapacityControllerAction.RESIZE and result.resize_ratio > 0.5:
            result.splits = self._compute_splits(requested, result.approved)

        # Reject if too small
        if result.approved < requested * 0.01:
            result.action = CapacityControllerAction.REJECT
            result.reason = "Order too small after capacity adjustment"

        # Defer if insufficient headroom
        if result.resize_ratio < 0.3 and result.action != CapacityControllerAction.REJECT:
            result.action = CapacityControllerAction.DEFER

        self._results.append(result)
        return result

    def _compute_splits(self, total: float, per_slice: float) -> List[float]:
        """Compute order split sizes."""
        if per_slice <= 0:
            return [total]
        n = int(total / per_slice) + (1 if total % per_slice > 0 else 0)
        base = total / n
        return [base] * n

    def results(self) -> List[CapacityControlResult]:
        return list(self._results)

    def summary(self) -> Dict[str, Any]:
        if not self._results:
            return {"checks": 0}
        return {
            "total_checks": len(self._results),
            "proceeded": sum(1 for r in self._results if r.action == CapacityControllerAction.PROCEED),
            "resized": sum(1 for r in self._results if r.action == CapacityControllerAction.RESIZE),
            "split": sum(1 for r in self._results if r.splits),
            "deferred": sum(1 for r in self._results if r.action == CapacityControllerAction.DEFER),
            "rejected": sum(1 for r in self._results if r.action == CapacityControllerAction.REJECT),
            "avg_resize_ratio": sum(r.resize_ratio for r in self._results) / len(self._results),
        }
