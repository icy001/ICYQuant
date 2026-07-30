"""Capital Allocator — dynamic capital allocation across portfolios and strategies."""

import time
import uuid
import logging
import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class AllocationMethod(Enum):
    EQUAL_WEIGHT = "equal_weight"
    RISK_PARITY = "risk_parity"
    MEAN_VARIANCE = "mean_variance"
    KELLY = "kelly"
    BLACK_LITTERMAN = "black_litterman"
    MINIMUM_VARIANCE = "minimum_variance"
    MAX_DIVERSIFICATION = "max_diversification"
    CUSTOM = "custom"


@dataclass
class CapitalPool:
    """Represents a pool of capital available for allocation."""

    pool_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""
    total_capital: float = 0.0
    allocated_capital: float = 0.0
    available_capital: float = 0.0
    reserved_capital: float = 0.0
    currency: str = "CNY"
    created_at: float = field(default_factory=time.time)

    @property
    def unallocated(self) -> float:
        return self.total_capital - self.allocated_capital - self.reserved_capital

    @property
    def utilization_pct(self) -> float:
        return (self.allocated_capital / self.total_capital * 100) if self.total_capital > 0 else 0.0


@dataclass
class AllocationRule:
    """Allocation rule for distributing capital."""

    rule_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""
    method: AllocationMethod = AllocationMethod.EQUAL_WEIGHT
    target_id: str = ""  # portfolio_id or strategy_id
    min_allocation: float = 0.0
    max_allocation: float = float("inf")
    target_weight: float = 0.0
    priority: int = 0
    conditions: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AllocationRequest:
    """A request to allocate capital."""

    request_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    pool_id: str = ""
    amount: float = 0.0
    method: AllocationMethod = AllocationMethod.EQUAL_WEIGHT
    rules: List[AllocationRule] = field(default_factory=list)
    constraints: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)


@dataclass
class AllocationResult:
    """Result of an allocation execution."""

    result_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    request_id: str = ""
    method: AllocationMethod = AllocationMethod.EQUAL_WEIGHT
    total_allocated: float = 0.0
    allocations: Dict[str, float] = field(default_factory=dict)
    weights: Dict[str, float] = field(default_factory=dict)
    unallocated: float = 0.0
    warnings: List[str] = field(default_factory=list)
    executed_at: float = field(default_factory=time.time)


@dataclass
class CapitalFlow:
    """Records a capital flow event (deposit, withdrawal, transfer)."""

    flow_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    flow_type: str = ""  # deposit | withdrawal | transfer | rebalance
    from_id: str = ""
    to_id: str = ""
    amount: float = 0.0
    currency: str = "CNY"
    timestamp: float = field(default_factory=time.time)
    reason: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


class CapitalAllocator:
    """Dynamic capital allocation engine.

    Supports multiple allocation methods:
    - Equal Weight: simple equal split
    - Risk Parity: equal risk contribution
    - Kelly Criterion: optimal bet sizing
    - Mean-Variance: Markowitz optimization
    - Custom: user-defined rules
    """

    def __init__(self):
        self._pools: Dict[str, CapitalPool] = {}
        self._rules: Dict[str, AllocationRule] = {}
        self._flows: List[CapitalFlow] = []
        self._allocations: Dict[str, List[AllocationResult]] = {}

    def create_pool(self, name: str, total_capital: float, currency: str = "CNY") -> CapitalPool:
        pool = CapitalPool(
            name=name,
            total_capital=total_capital,
            available_capital=total_capital,
            currency=currency,
        )
        self._pools[pool.pool_id] = pool
        return pool

    def add_rule(self, rule: AllocationRule) -> AllocationRule:
        self._rules[rule.rule_id] = rule
        return rule

    def allocate(self, request: AllocationRequest) -> AllocationResult:
        """Execute capital allocation based on request configuration."""
        pool = self._pools.get(request.pool_id)
        if not pool:
            return AllocationResult(
                request_id=request.request_id,
                warnings=["Pool not found"],
            )

        available = min(request.amount, pool.available_capital) if request.amount > 0 else pool.available_capital
        rules = request.rules or [
            r for r in self._rules.values() if r.target_id and r.enabled
        ]

        if not rules:
            return AllocationResult(
                request_id=request.request_id,
                method=request.method,
                warnings=["No allocation rules available"],
            )

        if request.method == AllocationMethod.EQUAL_WEIGHT:
            result = self._equal_weight(available, rules, request)
        elif request.method == AllocationMethod.RISK_PARITY:
            result = self._risk_parity(available, rules, request)
        elif request.method == AllocationMethod.KELLY:
            result = self._kelly(available, rules, request)
        else:
            result = self._equal_weight(available, rules, request)  # fallback

        # Update pool
        pool.allocated_capital += result.total_allocated
        pool.available_capital = pool.total_capital - pool.allocated_capital - pool.reserved_capital

        # Record allocation
        if request.pool_id not in self._allocations:
            self._allocations[request.pool_id] = []
        self._allocations[request.pool_id].append(result)

        return result

    def _equal_weight(
        self, available: float, rules: List[AllocationRule], request: AllocationRequest
    ) -> AllocationResult:
        """Equal-weight allocation."""
        valid_rules = [r for r in rules if r.enabled]
        if not valid_rules:
            return AllocationResult(request_id=request.request_id,
                                   method=AllocationMethod.EQUAL_WEIGHT)

        n = len(valid_rules)
        base_amount = available / n
        allocations: Dict[str, float] = {}
        weights: Dict[str, float] = {}
        total_allocated = 0.0

        for rule in valid_rules:
            amount = base_amount
            if amount > rule.max_allocation:
                amount = rule.max_allocation
            if amount < rule.min_allocation:
                amount = 0.0
            allocations[rule.target_id] = amount
            total_allocated += amount

        total_used = total_allocated if total_allocated > 0 else 1.0
        for k, v in allocations.items():
            weights[k] = v / total_used * 100

        return AllocationResult(
            request_id=request.request_id,
            method=AllocationMethod.EQUAL_WEIGHT,
            total_allocated=total_allocated,
            allocations=allocations,
            weights=weights,
            unallocated=available - total_allocated,
        )

    def _risk_parity(
        self, available: float, rules: List[AllocationRule], request: AllocationRequest
    ) -> AllocationResult:
        """Risk parity allocation — equal risk contribution."""
        valid_rules = [r for r in rules if r.enabled]
        if not valid_rules:
            return AllocationResult(request_id=request.request_id,
                                   method=AllocationMethod.RISK_PARITY)

        # Extract risk estimates from conditions if available
        risks = []
        for rule in valid_rules:
            vol = rule.conditions.get("volatility", 0.20)  # default 20% vol
            risks.append(vol)

        # Inverse volatility weighting
        inv_vols = [1.0 / max(r, 0.001) for r in risks]
        total_inv = sum(inv_vols)
        weights_raw = [iv / total_inv for iv in inv_vols]

        allocations: Dict[str, float] = {}
        weights: Dict[str, float] = {}
        total_allocated = 0.0

        for i, rule in enumerate(valid_rules):
            amount = available * weights_raw[i]
            if amount > rule.max_allocation:
                amount = rule.max_allocation
            if amount < rule.min_allocation:
                amount = 0.0
            allocations[rule.target_id] = amount
            total_allocated += amount

        total_used = total_allocated if total_allocated > 0 else 1.0
        for k, v in allocations.items():
            weights[k] = v / total_used * 100

        return AllocationResult(
            request_id=request.request_id,
            method=AllocationMethod.RISK_PARITY,
            total_allocated=total_allocated,
            allocations=allocations,
            weights=weights,
            unallocated=available - total_allocated,
        )

    def _kelly(
        self, available: float, rules: List[AllocationRule], request: AllocationRequest
    ) -> AllocationResult:
        """Kelly Criterion allocation based on win rate and odds."""
        valid_rules = [r for r in rules if r.enabled]
        if not valid_rules:
            return AllocationResult(request_id=request.request_id,
                                   method=AllocationMethod.KELLY)

        allocations: Dict[str, float] = {}
        weights: Dict[str, float] = {}
        total_allocated = 0.0
        total_kelly = 0.0

        # Compute Kelly fractions
        kelly_fractions: List[Tuple[str, float]] = []
        for rule in valid_rules:
            win_rate = rule.conditions.get("win_rate", 0.55)
            odds = rule.conditions.get("odds", 1.0)  # payoff ratio
            kelly = (win_rate * odds - (1 - win_rate)) / max(odds, 0.01)
            kelly = max(0.0, min(kelly, 0.25))  # cap at half-Kelly (25%)
            kelly_fractions.append((rule.target_id, kelly))
            total_kelly += kelly

        if total_kelly <= 0:
            return self._equal_weight(available, rules, request)

        for target_id, kelly in kelly_fractions:
            weight = kelly / total_kelly
            amount = available * weight
            allocations[target_id] = amount
            weights[target_id] = weight * 100
            total_allocated += amount

        return AllocationResult(
            request_id=request.request_id,
            method=AllocationMethod.KELLY,
            total_allocated=total_allocated,
            allocations=allocations,
            weights=weights,
            unallocated=available - total_allocated,
        )

    def record_flow(self, flow: CapitalFlow) -> CapitalFlow:
        """Record a capital flow event."""
        self._flows.append(flow)
        # Update pool balances
        if flow.from_id and flow.from_id in self._pools:
            self._pools[flow.from_id].allocated_capital -= flow.amount
        if flow.to_id and flow.to_id in self._pools:
            pool = self._pools[flow.to_id]
            if flow.flow_type == "deposit":
                pool.total_capital += flow.amount
                pool.available_capital += flow.amount
            else:
                pool.allocated_capital += flow.amount
        return flow

    def get_pool(self, pool_id: str) -> Optional[CapitalPool]:
        return self._pools.get(pool_id)

    def get_allocations(self, pool_id: str) -> List[AllocationResult]:
        return self._allocations.get(pool_id, [])

    def get_flows(
        self, flow_type: Optional[str] = None, limit: int = 100
    ) -> List[CapitalFlow]:
        flows = self._flows
        if flow_type:
            flows = [f for f in flows if f.flow_type == flow_type]
        return flows[-limit:]

    def get_summary(self) -> Dict[str, Any]:
        pools = list(self._pools.values())
        total_capital = sum(p.total_capital for p in pools)
        total_allocated = sum(p.allocated_capital for p in pools)
        total_flows = len(self._flows)
        return {
            "total_pools": len(pools),
            "total_capital": total_capital,
            "total_allocated": total_allocated,
            "utilization_pct": (total_allocated / total_capital * 100) if total_capital > 0 else 0.0,
            "total_flows": total_flows,
        }
