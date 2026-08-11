"""
Capital Decision — Unified decision output for capital management actions.

Decision types:
    ALLOCATE, INCREASE, REDUCE, HOLD, RESERVE, RELEASE, FREEZE, REBALANCE
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class CapitalDecisionType(str, Enum):
    ALLOCATE = "allocate"       # Initial allocation to a strategy
    INCREASE = "increase"       # Increase allocation
    REDUCE = "reduce"           # Reduce allocation
    HOLD = "hold"               # No change
    RESERVE = "reserve"         # Reserve capital for future use
    RELEASE = "release"         # Release reserved capital
    FREEZE = "freeze"           # Freeze capital (emergency)
    REBALANCE = "rebalance"     # Rebalance across strategies


class DecisionStatus(str, Enum):
    PROPOSED = "proposed"
    APPROVED = "approved"
    EXECUTED = "executed"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


@dataclass
class CapitalDecision:
    """A single capital management decision."""

    decision_id: str = field(default_factory=lambda: f"CD-{uuid.uuid4().hex[:8]}")
    decision_type: CapitalDecisionType = CapitalDecisionType.HOLD
    status: DecisionStatus = DecisionStatus.PROPOSED

    # Source
    strategy_id: str = ""
    account_id: str = ""
    portfolio_id: str = ""

    # Capital amounts
    current_capital: float = 0.0
    target_capital: float = 0.0
    delta_capital: float = 0.0

    # Rationale
    reason: str = ""
    priority_score: float = 0.0
    expected_return_impact: float = 0.0
    expected_risk_impact: float = 0.0

    # Guard results
    guard_result: str = "PENDING"
    guard_violations: List[str] = field(default_factory=list)

    # Audit
    created_at: str = ""
    approved_by: str = ""
    approved_at: str = ""
    executed_at: str = ""
    trace_id: str = ""

    # Metadata
    tags: Dict[str, str] = field(default_factory=dict)
    parent_decision_id: str = ""       # For linked decisions

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "type": self.decision_type.value,
            "status": self.status.value,
            "strategy_id": self.strategy_id,
            "account_id": self.account_id,
            "current_capital": self.current_capital,
            "target_capital": self.target_capital,
            "delta_capital": self.delta_capital,
            "reason": self.reason,
            "priority_score": self.priority_score,
            "guard_result": self.guard_result,
        }

    def approve(self, approver: str = "system") -> None:
        self.status = DecisionStatus.APPROVED
        self.approved_by = approver

    def execute(self) -> None:
        self.status = DecisionStatus.EXECUTED

    def reject(self, reason: str = "") -> None:
        self.status = DecisionStatus.REJECTED
        if reason:
            self.guard_violations.append(reason)


class CapitalDecisionEngine:
    """Generates and manages capital decisions."""

    def __init__(self):
        self._decisions: List[CapitalDecision] = []
        self._history: List[CapitalDecision] = []

    def create(
        self,
        decision_type: CapitalDecisionType,
        strategy_id: str = "",
        current_capital: float = 0.0,
        target_capital: float = 0.0,
        reason: str = "",
    ) -> CapitalDecision:
        decision = CapitalDecision(
            decision_type=decision_type,
            strategy_id=strategy_id,
            current_capital=current_capital,
            target_capital=target_capital,
            delta_capital=target_capital - current_capital,
            reason=reason,
        )
        self._decisions.append(decision)
        return decision

    def allocate(self, strategy_id: str, amount: float, reason: str = "") -> CapitalDecision:
        return self.create(CapitalDecisionType.ALLOCATE, strategy_id, 0, amount, reason)

    def increase(self, strategy_id: str, current: float, amount: float, reason: str = "") -> CapitalDecision:
        return self.create(CapitalDecisionType.INCREASE, strategy_id, current, current + amount, reason)

    def reduce(self, strategy_id: str, current: float, amount: float, reason: str = "") -> CapitalDecision:
        return self.create(CapitalDecisionType.REDUCE, strategy_id, current, max(0, current - amount), reason)

    def hold(self, strategy_id: str, current: float) -> CapitalDecision:
        return self.create(CapitalDecisionType.HOLD, strategy_id, current, current, "Holding")

    def rebalance(self, strategy_id: str, current: float, target: float, reason: str = "") -> CapitalDecision:
        return self.create(CapitalDecisionType.REBALANCE, strategy_id, current, target, reason)

    def freeze(self, strategy_id: str, current: float, reason: str = "Emergency freeze") -> CapitalDecision:
        return self.create(CapitalDecisionType.FREEZE, strategy_id, current, current, reason)

    def pending(self) -> List[CapitalDecision]:
        return [d for d in self._decisions if d.status == DecisionStatus.PROPOSED]

    def history(self) -> List[CapitalDecision]:
        return list(self._history)

    def execute_all_approved(self) -> int:
        count = 0
        for d in self._decisions:
            if d.status == DecisionStatus.APPROVED:
                d.execute()
                self._history.append(d)
                count += 1
        self._decisions = [d for d in self._decisions if d.status == DecisionStatus.PROPOSED]
        return count
