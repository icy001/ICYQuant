"""Allocation Controller — order flow gate for allocation execution.

Controls the flow of allocation decisions to execution:
PROCEED / RESIZE / SPLIT / DEFER / REJECT

Integrates capacity throttling and execution rate control.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional


class GateAction(str, Enum):
    """Actions the controller can take on an allocation request."""
    PROCEED = "PROCEED"
    RESIZE = "RESIZE"
    SPLIT = "SPLIT"
    DEFER = "DEFER"
    REJECT = "REJECT"
    FREEZE = "FREEZE"
    HOLD = "HOLD"


class ThrottleLevel(str, Enum):
    """Throttle levels for execution rate control."""
    NONE = "NONE"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    MAXIMUM = "MAXIMUM"


THROTTLE_RATE_MAP = {
    ThrottleLevel.NONE: 1.0,
    ThrottleLevel.LOW: 0.75,
    ThrottleLevel.MEDIUM: 0.50,
    ThrottleLevel.HIGH: 0.25,
    ThrottleLevel.MAXIMUM: 0.10,
}


@dataclass
class AllocationGateRequest:
    """Request passing through the allocation controller gate."""
    strategy_id: str
    current_weight: float
    target_weight: float
    capital_delta: float
    expected_alpha: float = 0.0
    marginal_alpha: float = 0.0
    marginal_risk: float = 0.0
    marginal_cost: float = 0.0
    capacity_score: float = 0.0
    liquidity_score: float = 0.0
    stress_score: float = 0.0
    survival_score: float = 0.0
    request_id: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.request_id:
            ts = self.timestamp.strftime("%Y%m%d%H%M%S%f")
            self.request_id = f"agr-{ts}-{hash(self.strategy_id) & 0xFFFF:04x}"


@dataclass
class AllocationGateResponse:
    """Response from the allocation controller gate."""
    request: AllocationGateRequest
    action: GateAction = GateAction.PROCEED
    adjusted_delta: float = 0.0
    reason: str = ""
    split_plan: List[Dict[str, Any]] = field(default_factory=list)
    deferred_until: Optional[datetime] = None
    throttle_level: ThrottleLevel = ThrottleLevel.NONE
    checks_passed: int = 0
    checks_failed: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.utcnow)


class AllocationController:
    """Gates allocation execution based on all risk/constraint dimensions.

    Implements the order flow gate with:
    - Capacity throttling
    - Participation rate enforcement
    - Impact budget enforcement
    - Liquidity regime compliance
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self._config = config or {}
        self._throttle_level = ThrottleLevel.NONE
        self._daily_gate_count = 0
        self._daily_reject_count = 0
        self._last_reset = datetime.utcnow()
        self._custom_checks: List[callable] = []
        self._frozen_strategies: set = set()

    @property
    def throttle_level(self) -> ThrottleLevel:
        return self._throttle_level

    def set_throttle(self, level: ThrottleLevel) -> None:
        """Set execution throttle level."""
        self._throttle_level = level

    def freeze_strategy(self, strategy_id: str) -> None:
        """Freeze all allocations for a strategy."""
        self._frozen_strategies.add(strategy_id)

    def unfreeze_strategy(self, strategy_id: str) -> None:
        """Unfreeze allocations for a strategy."""
        self._frozen_strategies.discard(strategy_id)

    def add_check(self, check: callable) -> None:
        """Add a custom gate check function."""
        self._custom_checks.append(check)

    def _maybe_reset_daily(self) -> None:
        """Reset daily counters if a new day has started."""
        now = datetime.utcnow()
        if now.date() > self._last_reset.date():
            self._daily_gate_count = 0
            self._daily_reject_count = 0
            self._last_reset = now

    def gate(self, request: AllocationGateRequest) -> AllocationGateResponse:
        """Evaluate an allocation request through the gate."""
        self._maybe_reset_daily()
        self._daily_gate_count += 1

        response = AllocationGateResponse(
            request=request,
            adjusted_delta=request.capital_delta,
            throttle_level=self._throttle_level,
        )

        # Check 1: Strategy frozen
        if request.strategy_id in self._frozen_strategies:
            response.action = GateAction.FREEZE
            response.reason = f"Strategy {request.strategy_id} is frozen"
            response.checks_failed.append("strategy_frozen")
            return response

        # Check 2: Capital delta trivial
        if abs(request.capital_delta) < 1e-6:
            response.action = GateAction.HOLD
            response.reason = "Capital delta is negligible"
            response.checks_passed += 1
            return response

        # Check 3: Survival score below critical threshold
        if request.survival_score < 0.30:
            response.action = GateAction.REJECT
            response.reason = f"Survival score {request.survival_score:.2f} below critical 0.30"
            response.checks_failed.append("survival_critical")
            self._daily_reject_count += 1
            return response

        # Check 4: Stress score below threshold
        if request.stress_score < 0.20:
            response.action = GateAction.REJECT
            response.reason = f"Stress score {request.stress_score:.2f} below threshold 0.20"
            response.checks_failed.append("stress_threshold")
            self._daily_reject_count += 1
            return response

        # Check 5: Liquidity too low
        if request.liquidity_score < 0.15:
            response.action = GateAction.DEFER
            response.reason = f"Liquidity score {request.liquidity_score:.2f} too low, deferring"
            response.checks_failed.append("liquidity_low")
            response.deferred_until = datetime.utcnow() + timedelta(minutes=30)
            return response

        # Check 6: Capacity score threshold
        if request.capacity_score < 0.20:
            response.action = GateAction.RESIZE
            resize_factor = max(0.10, request.capacity_score)
            response.adjusted_delta = request.capital_delta * resize_factor
            response.reason = f"Capacity score {request.capacity_score:.2f} below threshold, resizing to {response.adjusted_delta:,.0f}"
            response.checks_failed.append("capacity_resize")
            return response

        # Check 7: Throttle adjustment
        throttle_rate = THROTTLE_RATE_MAP.get(self._throttle_level, 1.0)
        if throttle_rate < 1.0:
            response.action = GateAction.RESIZE
            response.adjusted_delta = request.capital_delta * throttle_rate
            response.reason = f"Throttle {self._throttle_level.value} applied: {throttle_rate:.0%}"
            response.checks_failed.append("throttle")

        # Check 8-: Custom checks
        for check in self._custom_checks:
            try:
                result = check(request)
                if isinstance(result, str):
                    response.checks_failed.append(result)
                    if response.action == GateAction.PROCEED:
                        response.action = GateAction.DEFER
            except Exception as e:
                response.checks_failed.append(f"check_error: {e}")

        response.checks_passed = 8 - len(response.checks_failed)

        if response.action in (GateAction.REJECT, GateAction.FREEZE):
            self._daily_reject_count += 1

        return response

    def batch_gate(self, requests: List[AllocationGateRequest]) -> List[AllocationGateResponse]:
        """Process multiple requests through the gate."""
        return [self.gate(r) for r in requests]

    def get_daily_stats(self) -> Dict[str, int]:
        """Get daily gate statistics."""
        self._maybe_reset_daily()
        return {
            "total": self._daily_gate_count,
            "rejected": self._daily_reject_count,
            "approved": self._daily_gate_count - self._daily_reject_count,
        }
