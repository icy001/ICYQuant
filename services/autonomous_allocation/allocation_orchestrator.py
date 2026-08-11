"""Allocation Orchestrator — batch orchestration across portfolio.

Coordinates allocation decisions across all strategies simultaneously,
ensuring portfolio-level constraints are respected.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class OrchestrationRequest:
    """Batch orchestration request for multiple strategies."""
    strategy_requests: List[Dict[str, Any]] = field(default_factory=list)
    total_capital: float = 0.0
    reserve_ratio: float = 0.10
    buffer_ratio: float = 0.05
    risk_budget: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OrchestrationResult:
    """Result of a batch orchestration."""
    request: OrchestrationRequest
    allocations: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    total_allocated: float = 0.0
    total_reserved: float = 0.0
    total_buffered: float = 0.0
    remaining_capital: float = 0.0
    constraint_violations: List[str] = field(default_factory=list)
    status: str = "PENDING"
    timestamp: datetime = field(default_factory=datetime.utcnow)
    trace_id: str = ""

    @property
    def deployable_capital(self) -> float:
        return self.request.total_capital - self.total_reserved - self.total_buffered

    @property
    def allocation_ratio(self) -> float:
        if self.deployable_capital <= 0:
            return 0.0
        return self.total_allocated / self.deployable_capital


class AllocationOrchestrator:
    """Orchestrates allocation decisions across the entire portfolio.

    Ensures:
    - Total allocation ≤ deployable capital
    - Reserve and buffer requirements met
    - Portfolio-level constraints respected
    - Priority-weighted allocation when over-subscribed
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self._config = config or {}
        self._default_reserve_ratio = self._config.get("reserve_ratio", 0.10)
        self._default_buffer_ratio = self._config.get("buffer_ratio", 0.05)
        self._max_allocation_ratio = self._config.get("max_allocation_ratio", 0.95)
        self._orchestration_count = 0

    @property
    def orchestration_count(self) -> int:
        return self._orchestration_count

    def orchestrate(self, request: OrchestrationRequest) -> OrchestrationResult:
        """Execute batch orchestration across all strategy requests."""
        result = OrchestrationResult(
            request=request,
            trace_id=self._generate_trace_id(),
            status="PROCESSING",
        )

        # Compute reserve and buffer
        reserve_amount = request.total_capital * request.reserve_ratio
        buffer_amount = request.total_capital * request.buffer_ratio
        deployable = request.total_capital - reserve_amount - buffer_amount

        result.total_reserved = reserve_amount
        result.total_buffered = buffer_amount

        # Sum requested allocations
        requested_total = sum(
            r.get("capital_delta", 0) + r.get("current_capital", 0)
            for r in request.strategy_requests
            if r.get("capital_delta", 0) > 0
        )

        # Track existing allocation
        existing_total = sum(
            r.get("current_capital", 0) for r in request.strategy_requests
        )

        # Cap at max allocation ratio
        max_allocable = deployable * self._max_allocation_ratio
        new_capital_available = max(0, max_allocable - existing_total)

        allocations = {}

        if requested_total <= existing_total + new_capital_available:
            # All requests can be satisfied
            for req in request.strategy_requests:
                sid = req.get("strategy_id", "")
                delta = req.get("capital_delta", 0)
                current = req.get("current_capital", 0)
                target = current + delta
                allocations[sid] = {
                    "strategy_id": sid,
                    "current_capital": current,
                    "requested_delta": delta,
                    "allocated_delta": delta,
                    "target_capital": target,
                    "status": "ALLOCATED",
                }
        else:
            # Over-subscribed — priority-weighted proportional allocation
            allocations = self._allocate_with_priority(
                request.strategy_requests, new_capital_available
            )

        result.allocations = allocations
        result.total_allocated = sum(
            a.get("target_capital", 0) for a in allocations.values()
        )
        result.remaining_capital = deployable - result.total_allocated
        result.status = "COMPLETE"

        self._orchestration_count += 1
        return result

    def _allocate_with_priority(self, strategy_requests: List[Dict[str, Any]],
                                available: float) -> Dict[str, Dict[str, Any]]:
        """Allocate limited capital using priority-weighted proportional method."""
        if available <= 0:
            return {
                r.get("strategy_id", ""): {
                    "strategy_id": r.get("strategy_id", ""),
                    "current_capital": r.get("current_capital", 0),
                    "requested_delta": r.get("capital_delta", 0),
                    "allocated_delta": 0,
                    "target_capital": r.get("current_capital", 0),
                    "status": "NO_CAPACITY",
                }
                for r in strategy_requests
            }

        # Compute priority scores
        scored = []
        for r in strategy_requests:
            priority = self._compute_priority(r)
            delta = max(0, r.get("capital_delta", 0))
            scored.append((r, priority, delta))

        scored.sort(key=lambda x: x[1], reverse=True)

        total_priority = sum(s[1] for s in scored)
        allocations = {}
        remaining = available

        for i, (req, priority, delta) in enumerate(scored):
            sid = req.get("strategy_id", "")
            current = req.get("current_capital", 0)

            if total_priority > 0:
                share = available * (priority / total_priority)
            else:
                share = 0

            allocated_delta = min(share, delta, remaining)
            target = current + allocated_delta

            allocations[sid] = {
                "strategy_id": sid,
                "current_capital": current,
                "requested_delta": delta,
                "allocated_delta": allocated_delta,
                "target_capital": target,
                "priority_score": priority,
                "status": "ALLOCATED" if allocated_delta > 0 else "NO_CAPACITY",
            }
            remaining -= allocated_delta

        return allocations

    def _compute_priority(self, request: Dict[str, Any]) -> float:
        """Compute allocation priority score for a strategy request.

        Weighted: 35% alpha + 25% capacity + 20% liquidity + 10% risk + 10% survival
        """
        alpha = request.get("alpha_score", 0.5)
        capacity = request.get("capacity_score", 0.5)
        liquidity = request.get("liquidity_score", 0.5)
        risk = request.get("risk_score", 0.5)
        survival = request.get("survival_score", 0.5)

        priority = (
            0.35 * alpha +
            0.25 * capacity +
            0.20 * liquidity +
            0.10 * risk +
            0.10 * survival
        )
        return max(0.0, min(1.0, priority))

    def _generate_trace_id(self) -> str:
        """Generate a unique trace ID."""
        ts = datetime.utcnow().strftime("%Y%m%d%H%M%S%f")
        return f"orch-{ts}-{self._orchestration_count:06d}"

    def validate_orchestration(self, result: OrchestrationResult,
                               max_allocation: Optional[float] = None) -> List[str]:
        """Validate that orchestration result respects all portfolio constraints."""
        violations = []

        deployable = result.deployable_capital
        if result.total_allocated > deployable:
            violations.append(
                f"Over-allocated: {result.total_allocated:,.0f} > deployable {deployable:,.0f}"
            )

        if max_allocation is not None and result.total_allocated > max_allocation:
            violations.append(
                f"Max allocation exceeded: {result.total_allocated:,.0f} > {max_allocation:,.0f}"
            )

        if result.total_allocated < 0:
            violations.append("Negative total allocation")

        return violations
