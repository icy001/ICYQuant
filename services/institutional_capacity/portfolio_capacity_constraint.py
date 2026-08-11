"""
Portfolio Capacity Constraint — Enforces portfolio-level capacity constraints.

Handles constraints that cannot be resolved at the individual strategy level,
including aggregate asset limits, factor exposure caps, and execution bandwidth.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple


class ConstraintType(str, Enum):
    """Types of portfolio-level capacity constraints."""
    AGGREGATE_DOLLAR = "aggregate_dollar"
    PER_ASSET = "per_asset"
    PER_VENUE = "per_venue"
    PER_FACTOR = "per_factor"
    EXECUTION_BANDWIDTH = "execution_bandwidth"
    REGULATORY = "regulatory"
    CUSTOM = "custom"


class ConstraintAction(str, Enum):
    ALLOW = "allow"
    RESIZE = "resize"
    DEFER = "defer"
    REJECT = "reject"


@dataclass
class ConstraintRule:
    """A single constraint rule evaluated against portfolio capacity."""
    rule_id: str = field(default_factory=lambda: f"PCR-{uuid.uuid4().hex[:8]}")
    constraint_type: ConstraintType = ConstraintType.CUSTOM
    name: str = ""
    description: str = ""

    limit: float = float("inf")
    current: float = 0.0
    utilization: float = 0.0

    is_binding: bool = False
    is_active: bool = True
    priority: int = 0  # lower = more important

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "constraint_type": self.constraint_type.value,
            "name": self.name,
            "limit": self.limit,
            "current": self.current,
            "utilization": round(self.utilization, 4),
            "is_binding": self.is_binding,
            "is_active": self.is_active,
        }


@dataclass
class ConstraintCheckResult:
    """Result of checking a request against portfolio constraints."""

    request_id: str = ""
    constraint_type: ConstraintType = ConstraintType.CUSTOM
    rule_name: str = ""
    action: ConstraintAction = ConstraintAction.ALLOW
    limit: float = float("inf")
    requested: float = 0.0
    available: float = float("inf")
    resized_amount: Optional[float] = None
    reason: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def is_allowed(self) -> bool:
        return self.action == ConstraintAction.ALLOW

    @property
    def is_resized(self) -> bool:
        return self.action == ConstraintAction.RESIZE

    @property
    def is_rejected(self) -> bool:
        return self.action == ConstraintAction.REJECT

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "rule_name": self.rule_name,
            "action": self.action.value,
            "requested": self.requested,
            "available": self.available,
            "resized_amount": self.resized_amount,
            "reason": self.reason,
            "is_allowed": self.is_allowed,
        }


class PortfolioCapacityConstraint:
    """Manages and enforces portfolio-level capacity constraints."""

    def __init__(self):
        self._rules: Dict[str, ConstraintRule] = {}
        self._asset_limits: Dict[str, float] = {}
        self._factor_limits: Dict[str, float] = {}
        self._venue_limits: Dict[str, float] = {}
        self._aggregate_limit: float = float("inf")
        self._max_concurrent_orders: int = 50
        self._current_orders: int = 0
        self._check_history: List[ConstraintCheckResult] = []

    # ── Registration ──────────────────────────────────────────────

    def set_aggregate_limit(self, limit: float) -> None:
        self._aggregate_limit = limit

    def set_asset_limit(self, asset: str, limit: float) -> None:
        self._asset_limits[asset] = limit

    def set_factor_limit(self, factor: str, limit: float) -> None:
        self._factor_limits[factor] = limit

    def set_venue_limit(self, venue: str, limit: float) -> None:
        self._venue_limits[venue] = limit

    def set_max_concurrent_orders(self, max_orders: int) -> None:
        self._max_concurrent_orders = max_orders

    def add_rule(self, rule: ConstraintRule) -> None:
        self._rules[rule.rule_id] = rule

    def remove_rule(self, rule_id: str) -> None:
        self._rules.pop(rule_id, None)

    # ── Constraint Checking ───────────────────────────────────────

    def check_aggregate(self, request_id: str, amount: float,
                          current_total: float) -> ConstraintCheckResult:
        """Check against aggregate dollar capacity."""
        requested_total = current_total + amount
        available = self._aggregate_limit - current_total

        result = ConstraintCheckResult(
            request_id=request_id,
            constraint_type=ConstraintType.AGGREGATE_DOLLAR,
            rule_name="aggregate_dollar",
            requested=amount,
            limit=self._aggregate_limit,
            available=available,
        )

        if requested_total > self._aggregate_limit:
            if available > 0:
                result.action = ConstraintAction.RESIZE
                result.resized_amount = available
                result.reason = (
                    f"Aggregate limit {self._aggregate_limit:,.0f} exceeded: "
                    f"requested {amount:,.0f}, resized to {available:,.0f}"
                )
            else:
                result.action = ConstraintAction.REJECT
                result.reason = "Aggregate capacity fully utilized"
                result.available = 0.0

        self._check_history.append(result)
        return result

    def check_asset(self, request_id: str, asset: str, amount: float,
                     current_asset_total: float) -> ConstraintCheckResult:
        """Check against per-asset capacity limit."""
        limit = self._asset_limits.get(asset, float("inf"))
        requested_total = current_asset_total + amount
        available = limit - current_asset_total

        result = ConstraintCheckResult(
            request_id=request_id,
            constraint_type=ConstraintType.PER_ASSET,
            rule_name=f"asset:{asset}",
            requested=amount,
            limit=limit,
            available=available,
        )

        if limit != float("inf") and requested_total > limit:
            if available > 0:
                result.action = ConstraintAction.RESIZE
                result.resized_amount = available
                result.reason = f"Asset {asset} limit {limit:,.0f} exceeded"
            else:
                result.action = ConstraintAction.REJECT
                result.reason = f"Asset {asset} capacity fully utilized"
                result.available = 0.0

        self._check_history.append(result)
        return result

    def check_factor(self, request_id: str, factor: str, exposure: float,
                      current_factor_total: float) -> ConstraintCheckResult:
        """Check against per-factor exposure limit."""
        limit = self._factor_limits.get(factor, float("inf"))
        requested_total = current_factor_total + abs(exposure)
        available = limit - current_factor_total

        result = ConstraintCheckResult(
            request_id=request_id,
            constraint_type=ConstraintType.PER_FACTOR,
            rule_name=f"factor:{factor}",
            requested=abs(exposure),
            limit=limit,
            available=available,
        )

        if limit != float("inf") and requested_total > limit:
            if available > 0:
                result.action = ConstraintAction.RESIZE
                result.resized_amount = available
                result.reason = f"Factor {factor} limit {limit:.2f} exceeded"
            else:
                result.action = ConstraintAction.REJECT
                result.reason = f"Factor {factor} capacity fully utilized"
                result.available = 0.0

        self._check_history.append(result)
        return result

    def check_venue(self, request_id: str, venue: str, amount: float,
                     current_venue_total: float) -> ConstraintCheckResult:
        """Check against per-venue capacity limit."""
        limit = self._venue_limits.get(venue, float("inf"))
        requested_total = current_venue_total + amount
        available = limit - current_venue_total

        result = ConstraintCheckResult(
            request_id=request_id,
            constraint_type=ConstraintType.PER_VENUE,
            rule_name=f"venue:{venue}",
            requested=amount,
            limit=limit,
            available=available,
        )

        if limit != float("inf") and requested_total > limit:
            if available > 0:
                result.action = ConstraintAction.RESIZE
                result.resized_amount = available
                result.reason = f"Venue {venue} limit {limit:,.0f} exceeded"
            else:
                result.action = ConstraintAction.REJECT
                result.reason = f"Venue {venue} capacity fully utilized"
                result.available = 0.0

        self._check_history.append(result)
        return result

    def check_execution_bandwidth(self, request_id: str) -> ConstraintCheckResult:
        """Check against max concurrent order limit."""
        available = self._max_concurrent_orders - self._current_orders

        result = ConstraintCheckResult(
            request_id=request_id,
            constraint_type=ConstraintType.EXECUTION_BANDWIDTH,
            rule_name="execution_bandwidth",
            requested=1,
            limit=self._max_concurrent_orders,
            available=available,
        )

        if self._current_orders >= self._max_concurrent_orders:
            result.action = ConstraintAction.DEFER
            result.reason = f"Max concurrent orders ({self._max_concurrent_orders}) reached"
            result.available = 0.0

        self._check_history.append(result)
        return result

    def reserve_order_slot(self) -> bool:
        """Reserve one concurrent order slot. Returns False if full."""
        if self._current_orders >= self._max_concurrent_orders:
            return False
        self._current_orders += 1
        return True

    def release_order_slot(self) -> None:
        self._current_orders = max(0, self._current_orders - 1)

    # ── Full Pipeline Check ──────────────────────────────────────

    def full_check(self,
                   request_id: str,
                   amount: float,
                   asset: str,
                   factors: Optional[Dict[str, float]] = None,
                   venue: str = "",
                   current_total: float = 0.0,
                   current_asset_total: float = 0.0,
                   current_factor_totals: Optional[Dict[str, float]] = None,
                   current_venue_total: float = 0.0) -> List[ConstraintCheckResult]:
        """Run all applicable constraint checks and return collective result."""
        results: List[ConstraintCheckResult] = []
        current_factor_totals = current_factor_totals or {}

        # 1. Aggregate dollar
        results.append(self.check_aggregate(request_id, amount, current_total))

        # 2. Per asset
        if asset:
            results.append(self.check_asset(request_id, asset, amount, current_asset_total))

        # 3. Per factor
        if factors:
            for factor_name, exposure in factors.items():
                ft = current_factor_totals.get(factor_name, 0.0)
                results.append(self.check_factor(request_id, factor_name, exposure, ft))

        # 4. Per venue
        if venue:
            results.append(self.check_venue(request_id, venue, amount, current_venue_total))

        # 5. Execution bandwidth
        results.append(self.check_execution_bandwidth(request_id))

        return results

    def worst_action(self, results: List[ConstraintCheckResult]) -> ConstraintAction:
        """Return the most restrictive action from a list of results."""
        actions = [r.action for r in results]
        priority = {
            ConstraintAction.REJECT: 0,
            ConstraintAction.RESIZE: 1,
            ConstraintAction.DEFER: 2,
            ConstraintAction.ALLOW: 3,
        }
        return min(actions, key=lambda a: priority.get(a, 999)) if actions else ConstraintAction.ALLOW

    def effective_amount(self, results: List[ConstraintCheckResult],
                          original_amount: float) -> float:
        """Compute the effective amount after resize constraints."""
        amounts = []
        for r in results:
            if r.action == ConstraintAction.REJECT:
                return 0.0
            if r.action == ConstraintAction.RESIZE and r.resized_amount is not None:
                amounts.append(r.resized_amount)
        return min(amounts) if amounts else original_amount

    # ── Queries ──────────────────────────────────────────────────

    def get_rule(self, rule_id: str) -> Optional[ConstraintRule]:
        return self._rules.get(rule_id)

    def active_rules(self) -> List[ConstraintRule]:
        return [r for r in self._rules.values() if r.is_active]

    def binding_rules(self) -> List[ConstraintRule]:
        return [r for r in self._rules.values() if r.is_active and r.is_binding]

    def utilization_report(self) -> Dict[str, Any]:
        return {
            "aggregate": {
                "limit": self._aggregate_limit,
                "current": sum(
                    r.current for r in self._rules.values()
                    if r.constraint_type == ConstraintType.AGGREGATE_DOLLAR
                ),
            },
            "asset_limits": {
                asset: {"limit": limit}
                for asset, limit in self._asset_limits.items()
            },
            "factor_limits": {
                factor: {"limit": limit}
                for factor, limit in self._factor_limits.items()
            },
            "venue_limits": {
                venue: {"limit": limit}
                for venue, limit in self._venue_limits.items()
            },
            "execution_bandwidth": {
                "max": self._max_concurrent_orders,
                "current": self._current_orders,
                "available": self._max_concurrent_orders - self._current_orders,
            },
        }

    def recent_checks(self, limit: int = 100) -> List[Dict[str, Any]]:
        return [r.to_dict() for r in self._check_history[-limit:]]

    def summary(self) -> Dict[str, Any]:
        return {
            "active_rules": len(self.active_rules()),
            "binding_rules": len(self.binding_rules()),
            "aggregate_limit": self._aggregate_limit,
            "asset_limits_count": len(self._asset_limits),
            "factor_limits_count": len(self._factor_limits),
            "venue_limits_count": len(self._venue_limits),
            "execution_slots": {
                "max": self._max_concurrent_orders,
                "used": self._current_orders,
            },
        }
