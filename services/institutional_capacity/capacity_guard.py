"""
Capacity Guard — Safety gate that validates capacity decisions before execution.

Acts as the final checkpoint: ALLOW, RESIZE, DEFER, or REJECT.
Validates capital, risk, capacity, liquidity, and autonomy constraints.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from .capacity_intelligence import CapacitySnapshot


class GuardVerdict(str, Enum):
    ALLOW = "allow"
    RESIZE = "resize"
    DEFER = "defer"
    REJECT = "reject"


class GuardReason(str, Enum):
    PASSED_ALL = "passed_all"
    CAPITAL_LIMIT_EXCEEDED = "capital_limit_exceeded"
    RISK_LIMIT_EXCEEDED = "risk_limit_exceeded"
    CAPACITY_EXCEEDED = "capacity_exceeded"
    LIQUIDITY_INSUFFICIENT = "liquidity_insufficient"
    AUTONOMY_VIOLATION = "autonomy_violation"
    REGULATORY_BLOCK = "regulatory_block"
    POSITION_LIMIT = "position_limit"
    DAILY_LIMIT = "daily_limit"
    ORDER_LIMIT = "order_limit"


@dataclass
class GuardCheck:
    """A single check performed by the guard."""

    check_id: str = field(default_factory=lambda: f"GC-{uuid.uuid4().hex[:8]}")
    name: str = ""
    reason: GuardReason = GuardReason.PASSED_ALL
    verdict: GuardVerdict = GuardVerdict.ALLOW
    passed: bool = True

    limit: float = float("inf")
    current: float = 0.0
    requested: float = 0.0
    available: float = float("inf")
    message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "passed": self.passed,
            "verdict": self.verdict.value,
            "reason": self.reason.value,
            "limit": self.limit,
            "current": self.current,
            "requested": self.requested,
            "available": self.available,
            "message": self.message,
        }


@dataclass
class GuardResult:
    """Result of a full guard validation cycle."""

    result_id: str = field(default_factory=lambda: f"GR-{uuid.uuid4().hex[:8]}")
    strategy_id: str = ""
    asset: str = ""
    requested_amount: float = 0.0

    verdict: GuardVerdict = GuardVerdict.ALLOW
    resized_amount: Optional[float] = None
    defer_until: Optional[datetime] = None
    rejection_reason: str = ""

    checks: List[GuardCheck] = field(default_factory=list)
    all_checks_passed: bool = True
    failed_checks: List[GuardCheck] = field(default_factory=list)

    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def effective_amount(self) -> float:
        if self.verdict == GuardVerdict.REJECT:
            return 0.0
        if self.verdict == GuardVerdict.RESIZE and self.resized_amount is not None:
            return self.resized_amount
        return self.requested_amount

    def to_dict(self) -> Dict[str, Any]:
        return {
            "result_id": self.result_id,
            "strategy_id": self.strategy_id,
            "asset": self.asset,
            "requested_amount": self.requested_amount,
            "verdict": self.verdict.value,
            "effective_amount": self.effective_amount,
            "resized_amount": self.resized_amount,
            "rejection_reason": self.rejection_reason,
            "checks_passed": self.all_checks_passed,
            "failed_checks": [c.to_dict() for c in self.failed_checks],
        }


class CapacityGuard:
    """Final safety gate for capacity deployment decisions.

    Checks in order of priority:
    1. Capital limits (account, strategy, max position)
    2. Risk limits (VaR, exposure, concentration)
    3. Capacity limits (strategy capacity headroom)
    4. Liquidity limits (market depth, participation)
    5. Autonomy / deployment limits (per-day, per-order)
    """

    def __init__(self):
        # Limits
        self.max_order_size: float = float("inf")
        self.max_position_size: float = float("inf")
        self.max_daily_volume: float = float("inf")
        self.max_strategy_exposure: float = float("inf")
        self.max_account_exposure: float = float("inf")
        self.max_impact_bps: float = 15.0
        self.max_participation: float = 0.10
        self.min_liquidity_score: float = 20.0

        # State
        self._current_position: float = 0.0
        self._daily_volume: float = 0.0
        self._strategy_exposure: float = 0.0
        self._account_exposure: float = 0.0
        self._results: List[GuardResult] = []

        # Auto-resize config
        self._auto_resize: bool = True
        self._min_fill_rate: float = 0.10

    # ── State Updates ─────────────────────────────────────────────

    def set_position(self, amount: float) -> None:
        self._current_position = amount

    def set_daily_volume(self, amount: float) -> None:
        self._daily_volume = amount

    def set_strategy_exposure(self, amount: float) -> None:
        self._strategy_exposure = amount

    def set_account_exposure(self, amount: float) -> None:
        self._account_exposure = amount

    # ── Validation ────────────────────────────────────────────────

    def validate(self,
                 strategy_id: str,
                 asset: str,
                 requested_amount: float,
                 snapshot: Optional[CapacitySnapshot] = None) -> GuardResult:
        """Run all guard checks and return verdict."""

        result = GuardResult(
            strategy_id=strategy_id,
            asset=asset,
            requested_amount=requested_amount,
        )
        checks: List[GuardCheck] = []

        # Check 1: Order size limit
        checks.append(self._check_order_size(requested_amount))

        # Check 2: Position limit
        checks.append(self._check_position(requested_amount))

        # Check 3: Daily volume limit
        checks.append(self._check_daily_volume(requested_amount))

        # Check 4: Strategy exposure
        checks.append(self._check_strategy_exposure(requested_amount))

        # Check 5: Account exposure
        checks.append(self._check_account_exposure(requested_amount))

        # Check 6: Impact budget
        if snapshot:
            checks.append(self._check_impact(snapshot))

        # Check 7: Participation rate
        if snapshot:
            checks.append(self._check_participation(snapshot))

        # Check 8: Liquidity score
        if snapshot:
            checks.append(self._check_liquidity(snapshot))

        # Determine overall verdict
        result.checks = checks
        result.failed_checks = [c for c in checks if not c.passed]
        result.all_checks_passed = len(result.failed_checks) == 0

        if result.all_checks_passed:
            result.verdict = GuardVerdict.ALLOW
        else:
            result.verdict = self._resolve_verdict(checks)

        # Compute effective amount
        if result.verdict == GuardVerdict.RESIZE:
            result.resized_amount = self._compute_resize_amount(checks, requested_amount)
        elif result.verdict == GuardVerdict.DEFER:
            result.defer_until = datetime.fromtimestamp(
                datetime.now(timezone.utc).timestamp() + 300,
                tz=timezone.utc,
            )
        elif result.verdict == GuardVerdict.REJECT:
            result.rejection_reason = "; ".join(
                c.message for c in result.failed_checks if c.message
            )

        self._results.append(result)
        return result

    # ── Individual Checks ─────────────────────────────────────────

    def _check_order_size(self, amount: float) -> GuardCheck:
        check = GuardCheck(
            name="order_size",
            reason=GuardReason.ORDER_LIMIT,
            limit=self.max_order_size,
            current=self._current_position,
            requested=amount,
            available=self.max_order_size,
        )
        if amount > self.max_order_size:
            check.passed = False
            check.verdict = GuardVerdict.RESIZE if self._auto_resize else GuardVerdict.REJECT
            check.message = f"Order {amount:,.0f} exceeds max order size {self.max_order_size:,.0f}"
        return check

    def _check_position(self, amount: float) -> GuardCheck:
        new_position = self._current_position + amount
        check = GuardCheck(
            name="position",
            reason=GuardReason.POSITION_LIMIT,
            limit=self.max_position_size,
            current=self._current_position,
            requested=amount,
            available=max(0, self.max_position_size - self._current_position),
        )
        if new_position > self.max_position_size:
            check.passed = False
            remaining = self.max_position_size - self._current_position
            if remaining > 0 and remaining / amount >= self._min_fill_rate:
                check.verdict = GuardVerdict.RESIZE
            else:
                check.verdict = GuardVerdict.REJECT
            check.message = (
                f"Position {new_position:,.0f} exceeds limit {self.max_position_size:,.0f}"
            )
        return check

    def _check_daily_volume(self, amount: float) -> GuardCheck:
        new_daily = self._daily_volume + amount
        check = GuardCheck(
            name="daily_volume",
            reason=GuardReason.DAILY_LIMIT,
            limit=self.max_daily_volume,
            current=self._daily_volume,
            requested=amount,
            available=max(0, self.max_daily_volume - self._daily_volume),
        )
        if new_daily > self.max_daily_volume:
            check.passed = False
            remaining = self.max_daily_volume - self._daily_volume
            if remaining > 0:
                check.verdict = GuardVerdict.RESIZE
            else:
                check.verdict = GuardVerdict.REJECT
            check.message = (
                f"Daily volume {new_daily:,.0f} exceeds limit {self.max_daily_volume:,.0f}"
            )
        return check

    def _check_strategy_exposure(self, amount: float) -> GuardCheck:
        new_exp = self._strategy_exposure + amount
        check = GuardCheck(
            name="strategy_exposure",
            reason=GuardReason.RISK_LIMIT_EXCEEDED,
            limit=self.max_strategy_exposure,
            current=self._strategy_exposure,
            requested=amount,
            available=max(0, self.max_strategy_exposure - self._strategy_exposure),
        )
        if new_exp > self.max_strategy_exposure:
            check.passed = False
            remaining = self.max_strategy_exposure - self._strategy_exposure
            if remaining > 0:
                check.verdict = GuardVerdict.RESIZE
            else:
                check.verdict = GuardVerdict.REJECT
            check.message = f"Strategy exposure {new_exp:,.0f} exceeds limit {self.max_strategy_exposure:,.0f}"
        return check

    def _check_account_exposure(self, amount: float) -> GuardCheck:
        new_exp = self._account_exposure + amount
        check = GuardCheck(
            name="account_exposure",
            reason=GuardReason.CAPITAL_LIMIT_EXCEEDED,
            limit=self.max_account_exposure,
            current=self._account_exposure,
            requested=amount,
            available=max(0, self.max_account_exposure - self._account_exposure),
        )
        if new_exp > self.max_account_exposure:
            check.passed = False
            remaining = self.max_account_exposure - self._account_exposure
            if remaining > 0:
                check.verdict = GuardVerdict.RESIZE
            else:
                check.verdict = GuardVerdict.REJECT
            check.message = f"Account exposure {new_exp:,.0f} exceeds limit {self.max_account_exposure:,.0f}"
        return check

    def _check_impact(self, snapshot: CapacitySnapshot) -> GuardCheck:
        check = GuardCheck(
            name="impact_budget",
            reason=GuardReason.CAPACITY_EXCEEDED,
            limit=self.max_impact_bps,
            current=0.0,
            requested=snapshot.expected_impact_bps,
            available=self.max_impact_bps,
        )
        if snapshot.expected_impact_bps > self.max_impact_bps:
            check.passed = False
            check.verdict = GuardVerdict.RESIZE if self._auto_resize else GuardVerdict.REJECT
            check.message = (
                f"Expected impact {snapshot.expected_impact_bps:.1f} bps > "
                f"budget {self.max_impact_bps:.1f} bps"
            )
        return check

    def _check_participation(self, snapshot: CapacitySnapshot) -> GuardCheck:
        participation = snapshot.get("participation_rate", 0.0)
        check = GuardCheck(
            name="participation_rate",
            reason=GuardReason.CAPACITY_EXCEEDED,
            limit=self.max_participation,
            current=0.0,
            requested=participation,
            available=self.max_participation,
        )
        if participation > self.max_participation:
            check.passed = False
            check.verdict = GuardVerdict.RESIZE if self._auto_resize else GuardVerdict.REJECT
            check.message = f"Participation {participation:.4f} exceeds limit {self.max_participation}"
        return check

    def _check_liquidity(self, snapshot: CapacitySnapshot) -> GuardCheck:
        score = snapshot.liquidity_score
        check = GuardCheck(
            name="liquidity_score",
            reason=GuardReason.LIQUIDITY_INSUFFICIENT,
            limit=self.min_liquidity_score,
            current=score,
            requested=score,
            available=self.min_liquidity_score,
        )
        if score < self.min_liquidity_score:
            check.passed = False
            check.verdict = GuardVerdict.DEFER
            check.message = f"Liquidity score {(score):.1f} below minimum {self.min_liquidity_score:.1f}"
        return check

    # ── Resolution ────────────────────────────────────────────────

    def _resolve_verdict(self, checks: List[GuardCheck]) -> GuardVerdict:
        """Determine the most restrictive verdict from all failed checks."""
        failed = [c for c in checks if not c.passed]
        verdict_priority = {
            GuardVerdict.REJECT: 0,
            GuardVerdict.DEFER: 1,
            GuardVerdict.RESIZE: 2,
            GuardVerdict.ALLOW: 3,
        }
        if not failed:
            return GuardVerdict.ALLOW
        return min(failed, key=lambda c: verdict_priority.get(c.verdict, 999)).verdict

    def _compute_resize_amount(self, checks: List[GuardCheck], original: float) -> float:
        """Compute the largest allowable amount from failing resize checks."""
        available_amounts = [original]
        for c in checks:
            if not c.passed and c.verdict == GuardVerdict.RESIZE:
                if c.reason == GuardReason.ORDER_LIMIT:
                    available_amounts.append(self.max_order_size)
                elif c.reason == GuardReason.POSITION_LIMIT:
                    available_amounts.append(self.max_position_size - self._current_position)
                elif c.reason == GuardReason.DAILY_LIMIT:
                    available_amounts.append(self.max_daily_volume - self._daily_volume)
                elif c.reason == GuardReason.RISK_LIMIT_EXCEEDED:
                    available_amounts.append(self.max_strategy_exposure - self._strategy_exposure)
                elif c.reason == GuardReason.CAPITAL_LIMIT_EXCEEDED:
                    available_amounts.append(self.max_account_exposure - self._account_exposure)
                elif c.reason == GuardReason.CAPACITY_EXCEEDED:
                    available_amounts.append(original * 0.50)  # halve for impact/participation
                elif c.available != float("inf"):
                    available_amounts.append(c.available)
        return max(0.0, min(available_amounts))

    # ── Query ─────────────────────────────────────────────────────

    def recent_results(self, limit: int = 50) -> List[GuardResult]:
        return self._results[-limit:]

    def approval_rate(self) -> float:
        if not self._results:
            return 1.0
        allowed = sum(1 for r in self._results if r.verdict == GuardVerdict.ALLOW)
        return allowed / len(self._results)

    def reject_rate(self) -> float:
        if not self._results:
            return 0.0
        rejected = sum(1 for r in self._results if r.verdict == GuardVerdict.REJECT)
        return rejected / len(self._results)

    def summary(self) -> Dict[str, Any]:
        return {
            "checks_total": len(self._results),
            "approval_rate": round(self.approval_rate(), 4),
            "reject_rate": round(self.reject_rate(), 4),
            "limits": {
                "max_order_size": self.max_order_size,
                "max_position_size": self.max_position_size,
                "max_daily_volume": self.max_daily_volume,
                "max_strategy_exposure": self.max_strategy_exposure,
                "max_impact_bps": self.max_impact_bps,
                "max_participation": self.max_participation,
            },
        }
