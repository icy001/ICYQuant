"""
Capacity Decision — Decisions about capacity allocation, sizing, and execution.

Converts capacity analysis into actionable decisions:
- PROCEED: Execute at requested size
- RESIZE: Adjust amount based on constraints
- SPLIT: Break into smaller orders
- DEFER: Delay execution
- REJECT: Block execution entirely
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from .capacity_intelligence import CapacitySnapshot, CapacityState


class DecisionType(str, Enum):
    PROCEED = "proceed"
    RESIZE = "resize"
    SPLIT = "split"
    DEFER = "defer"
    REJECT = "reject"
    THROTTLE = "throttle"


class DecisionReason(str, Enum):
    """Why a decision was made."""
    CAPACITY_AVAILABLE = "capacity_available"
    CAPACITY_EXCEEDED = "capacity_exceeded"
    LIQUIDITY_INSUFFICIENT = "liquidity_insufficient"
    IMPACT_EXCEEDED = "impact_exceeded"
    PARTICIPATION_EXCEEDED = "participation_exceeded"
    BUDGET_EXCEEDED = "budget_exceeded"
    REGIME_RESTRICTED = "regime_restricted"
    THROTTLE_ACTIVE = "throttle_active"
    FROZEN = "frozen"
    CONSTRAINT_VIOLATION = "constraint_violation"


@dataclass
class CapacityDecision:
    """A decision about whether and how to deploy capital."""

    decision_id: str = field(default_factory=lambda: f"CD-{uuid.uuid4().hex[:8]}")
    decision_type: DecisionType = DecisionType.PROCEED
    reason: DecisionReason = DecisionReason.CAPACITY_AVAILABLE
    description: str = ""

    # Request context
    strategy_id: str = ""
    asset: str = ""
    requested_amount: float = 0.0
    original_amount: float = 0.0

    # Decision output
    approved_amount: float = 0.0
    resized_amount: Optional[float] = None
    split_orders: List[Dict[str, Any]] = field(default_factory=list)
    defer_until: Optional[datetime] = None
    rejection_reason: str = ""

    # Supporting data
    snapshot: Optional[CapacitySnapshot] = None
    utilization: float = 0.0
    expected_impact_bps: float = 0.0
    participation_rate: float = 0.0
    liquidity_score: float = 0.0

    # Metadata
    priority: int = 0
    ttl_seconds: int = 60  # decision validity period
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def is_approved(self) -> bool:
        return self.decision_type in (DecisionType.PROCEED, DecisionType.RESIZE, DecisionType.SPLIT)

    @property
    def is_blocked(self) -> bool:
        return self.decision_type in (DecisionType.DEFER, DecisionType.REJECT)

    @property
    def effective_amount(self) -> float:
        if self.decision_type == DecisionType.REJECT:
            return 0.0
        if self.decision_type == DecisionType.RESIZE and self.resized_amount is not None:
            return self.resized_amount
        return self.approved_amount

    @property
    def fill_rate(self) -> float:
        if self.requested_amount <= 0:
            return 1.0
        return self.effective_amount / self.requested_amount

    @property
    def is_expired(self) -> bool:
        if self.ttl_seconds <= 0:
            return False
        elapsed = (datetime.now(timezone.utc) - self.timestamp).total_seconds()
        return elapsed > self.ttl_seconds

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "decision_type": self.decision_type.value,
            "reason": self.reason.value,
            "description": self.description,
            "strategy_id": self.strategy_id,
            "asset": self.asset,
            "requested_amount": self.requested_amount,
            "approved_amount": self.approved_amount,
            "effective_amount": self.effective_amount,
            "fill_rate": round(self.fill_rate, 4),
            "utilization": round(self.utilization, 4),
            "expected_impact_bps": round(self.expected_impact_bps, 2),
            "participation_rate": round(self.participation_rate, 4),
            "liquidity_score": round(self.liquidity_score, 2),
            "is_approved": self.is_approved,
            "timestamp": self.timestamp.isoformat(),
        }


class CapacityDecisionEngine:
    """Generates capacity decisions from intelligence snapshots.

    Pipeline:
        Snapshot → Rules Engine → Decision (PROCEED/RESIZE/SPLIT/DEFER/REJECT)
    """

    def __init__(self):
        self._decisions: List[CapacityDecision] = []
        self._config: Dict[str, Any] = self._default_config()

    @staticmethod
    def _default_config() -> Dict[str, Any]:
        return {
            "max_participation_rate": 0.10,
            "max_impact_bps": 15.0,
            "min_liquidity_score": 20.0,
            "auto_resize": True,
            "resize_factor": 0.90,
            "max_split_orders": 5,
            "defer_duration_seconds": 300,
            "min_fill_rate": 0.10,
        }

    # ── Configuration ─────────────────────────────────────────────

    def configure(self, **kwargs) -> None:
        self._config.update(kwargs)

    # ── Decision Making ───────────────────────────────────────────

    def decide(self,
               strategy_id: str,
               asset: str,
               requested_amount: float,
               snapshot: CapacitySnapshot) -> CapacityDecision:
        """Generate a capacity decision from a snapshot."""

        decision = CapacityDecision(
            strategy_id=strategy_id,
            asset=asset,
            requested_amount=requested_amount,
            original_amount=requested_amount,
            snapshot=snapshot,
        )

        max_participation = self._config["max_participation_rate"]
        max_impact = self._config["max_impact_bps"]
        min_liquidity = self._config["min_liquidity_score"]

        # Rule 1: Frozen → REJECT
        if snapshot.state == CapacityState.FROZEN:
            decision.decision_type = DecisionType.REJECT
            decision.reason = DecisionReason.FROZEN
            decision.rejection_reason = "Strategy capacity is frozen"
            decision.approved_amount = 0.0
            self._decisions.append(decision)
            return decision

        # Rule 2: Regime restricted → THROTTLE or DEFER
        if snapshot.state == CapacityState.REJECTED:
            decision.decision_type = DecisionType.REJECT
            decision.reason = DecisionReason.REGIME_RESTRICTED
            decision.rejection_reason = f"Capacity rejected: {snapshot.rejection_reason}"
            decision.approved_amount = 0.0
            self._decisions.append(decision)
            return decision

        # Rule 3: Impact budget exceeded → RESIZE or REJECT
        if snapshot.expected_impact_bps > max_impact:
            if self._config["auto_resize"]:
                resize_ratio = max_impact / snapshot.expected_impact_bps
                resized = requested_amount * resize_ratio * self._config["resize_factor"]
                if resized / requested_amount >= self._config["min_fill_rate"]:
                    decision.decision_type = DecisionType.RESIZE
                    decision.reason = DecisionReason.IMPACT_EXCEEDED
                    decision.resized_amount = resized
                    decision.approved_amount = resized
                    decision.description = (
                        f"Resized from {requested_amount:,.0f} to {resized:,.0f} "
                        f"(impact {snapshot.expected_impact_bps:.1f} > {max_impact} bps)"
                    )
                else:
                    decision.decision_type = DecisionType.REJECT
                    decision.reason = DecisionReason.IMPACT_EXCEEDED
                    decision.approved_amount = 0.0
                    decision.rejection_reason = (
                        f"Impact {snapshot.expected_impact_bps:.1f} bps exceeds budget {max_impact} bps"
                    )
            else:
                decision.decision_type = DecisionType.REJECT
                decision.reason = DecisionReason.IMPACT_EXCEEDED
                decision.approved_amount = 0.0
                decision.rejection_reason = f"Impact {snapshot.expected_impact_bps:.1f} > {max_impact} bps"
            self._decisions.append(decision)
            return decision

        # Rule 4: Participation exceeded → RESIZE or REJECT
        participation = snapshot.get("participation_rate", 0.0)
        if participation > max_participation:
            if self._config["auto_resize"]:
                resize_ratio = max_participation / participation
                resized = requested_amount * resize_ratio * self._config["resize_factor"]
                if resized / requested_amount >= self._config["min_fill_rate"]:
                    decision.decision_type = DecisionType.RESIZE
                    decision.reason = DecisionReason.PARTICIPATION_EXCEEDED
                    decision.resized_amount = resized
                    decision.approved_amount = resized
                else:
                    decision.decision_type = DecisionType.REJECT
                    decision.reason = DecisionReason.PARTICIPATION_EXCEEDED
                    decision.approved_amount = 0.0
            else:
                decision.decision_type = DecisionType.REJECT
                decision.reason = DecisionReason.PARTICIPATION_EXCEEDED
                decision.approved_amount = 0.0
            self._decisions.append(decision)
            return decision

        # Rule 5: Low liquidity score → DEFER
        ls = snapshot.liquidity_score
        if ls < min_liquidity:
            decision.decision_type = DecisionType.DEFER
            decision.reason = DecisionReason.LIQUIDITY_INSUFFICIENT
            decision.defer_until = datetime.fromtimestamp(
                datetime.now(timezone.utc).timestamp() + self._config["defer_duration_seconds"],
                tz=timezone.utc,
            )
            decision.approved_amount = 0.0
            decision.description = f"Liquidity score {(ls):.1f} < minimum {(min_liquidity):.1f}"
            self._decisions.append(decision)
            return decision

        # Rule 6: Budget exceeded → RESIZE or REJECT
        if not snapshot.is_allocatable:
            decision.decision_type = DecisionType.REJECT
            decision.reason = DecisionReason.BUDGET_EXCEEDED
            decision.approved_amount = 0.0
            decision.rejection_reason = "Budget capacity exceeded"
            self._decisions.append(decision)
            return decision

        # Rule 7: Degraded → REDUCE size
        if snapshot.state == CapacityState.DEGRADED:
            degraded_amount = requested_amount * 0.70
            decision.decision_type = DecisionType.RESIZE
            decision.reason = DecisionReason.THROTTLE_ACTIVE
            decision.resized_amount = degraded_amount
            decision.approved_amount = degraded_amount
            decision.description = f"Degraded mode: reduced to {degraded_amount:,.0f}"
            self._decisions.append(decision)
            return decision

        # Rule 8: OK → PROCEED
        decision.decision_type = DecisionType.PROCEED
        decision.reason = DecisionReason.CAPACITY_AVAILABLE
        decision.approved_amount = requested_amount
        decision.description = "Capacity available, proceeding"

        # Check if splitting would be optimal (large order)
        if snapshot.executable_capital < requested_amount * 0.5:
            decision.decision_type = DecisionType.SPLIT
            decision.reason = DecisionReason.CAPACITY_EXCEEDED
            slices = min(self._config["max_split_orders"], max(2, int(requested_amount / max(snapshot.executable_capital, 1))))
            slice_amount = requested_amount / slices
            decision.split_orders = [
                {"slice": i + 1, "amount": slice_amount, "total_slices": slices}
                for i in range(slices)
            ]
            decision.description = f"Split into {slices} orders of {slice_amount:,.0f}"

        # Populate fields
        decision.participation_rate = participation
        decision.expected_impact_bps = snapshot.expected_impact_bps
        decision.liquidity_score = snapshot.liquidity_score
        decision.utilization = snapshot.utilization

        self._decisions.append(decision)
        return decision

    # ── Query ─────────────────────────────────────────────────────

    def recent_decisions(self, limit: int = 100) -> List[CapacityDecision]:
        return self._decisions[-limit:]

    def decisions_by_type(self, decision_type: DecisionType) -> List[CapacityDecision]:
        return [d for d in self._decisions if d.decision_type == decision_type]

    def decisions_by_strategy(self, strategy_id: str) -> List[CapacityDecision]:
        return [d for d in self._decisions if d.strategy_id == strategy_id]

    def pending_deferred(self) -> List[CapacityDecision]:
        now = datetime.now(timezone.utc)
        return [
            d for d in self._decisions
            if d.decision_type == DecisionType.DEFER
            and d.defer_until is not None
            and d.defer_until <= now
        ]

    def approval_rate(self) -> float:
        total = len(self._decisions)
        if total == 0:
            return 1.0
        approved = sum(1 for d in self._decisions if d.is_approved)
        return approved / total

    def avg_fill_rate(self) -> float:
        if not self._decisions:
            return 1.0
        return sum(d.fill_rate for d in self._decisions) / len(self._decisions)

    def summary(self) -> Dict[str, Any]:
        return {
            "total_decisions": len(self._decisions),
            "approval_rate": round(self.approval_rate(), 4),
            "avg_fill_rate": round(self.avg_fill_rate(), 4),
            "by_type": {
                dt.value: len(self.decisions_by_type(dt))
                for dt in DecisionType
            },
            "pending_deferred": len(self.pending_deferred()),
        }
