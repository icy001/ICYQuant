"""
Decision Result — Structured result from a governance decision.

Captures the outcome, reason, constraints, and metadata for any
decision evaluated through the Control Plane.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class DecisionOutcome(Enum):
    ALLOW = "allow"
    DENY = "deny"
    RESIZE = "resize"
    DEFER = "defer"
    REVIEW = "review"
    QUARANTINE = "quarantine"
    ROLLBACK = "rollback"
    HALT = "halt"


@dataclass
class DecisionConstraint:
    """A constraint applied to an allowed decision."""
    name: str
    value: Any
    reason: str
    limit_type: str = ""  # e.g., "hard", "soft", "advisory"


@dataclass
class DecisionResult:
    """
    Result of a governance decision evaluation.

    Contains the outcome (allow/deny/resize/etc.), constraints that
    were applied, the governing policy/autonomy context, and any
    explanation for the decision.
    """
    decision_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    outcome: DecisionOutcome = DecisionOutcome.ALLOW
    allowed: bool = True
    evaluated_at: float = field(default_factory=time.time)

    # Reason
    reason: Optional[str] = None

    # Applied constraints (for resized decisions)
    constraints: list[DecisionConstraint] = field(default_factory=list)
    resized_value: Optional[float] = None
    original_value: Optional[float] = None

    # Governance context
    policy_id: Optional[str] = None
    policy_version: Optional[str] = None
    autonomy_level: int = 0
    approval_required: bool = False
    approval_id: Optional[str] = None

    # Audit
    audit_entries: list[dict] = field(default_factory=list)
    trace_id: str = ""

    @property
    def decision(self):
        """Compatibility alias for outcome."""
        return self.outcome

    def add_constraint(self, name: str, value: Any, reason: str, limit_type: str = "hard"):
        self.constraints.append(DecisionConstraint(
            name=name, value=value, reason=reason, limit_type=limit_type
        ))

    def to_dict(self) -> dict:
        return {
            "decision_id": self.decision_id,
            "outcome": self.outcome.value,
            "allowed": self.allowed,
            "evaluated_at": self.evaluated_at,
            "reason": self.reason,
            "constraints": [
                {"name": c.name, "value": c.value, "reason": c.reason, "limit_type": c.limit_type}
                for c in self.constraints
            ],
            "resized_value": self.resized_value,
            "original_value": self.original_value,
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "autonomy_level": self.autonomy_level,
            "approval_required": self.approval_required,
            "approval_id": self.approval_id,
            "trace_id": self.trace_id,
        }

    @classmethod
    def allowed_result(cls, trace_id: str = "") -> "DecisionResult":
        return cls(outcome=DecisionOutcome.ALLOW, allowed=True, trace_id=trace_id)

    @classmethod
    def denied(cls, reason: str, trace_id: str = "") -> "DecisionResult":
        return cls(outcome=DecisionOutcome.DENY, allowed=False, reason=reason, trace_id=trace_id)

    @classmethod
    def deferred(cls, reason: str, trace_id: str = "") -> "DecisionResult":
        return cls(outcome=DecisionOutcome.DEFER, allowed=False, reason=reason, trace_id=trace_id)

    @classmethod
    def resized(cls, original: float, resized: float, reason: str, trace_id: str = "") -> "DecisionResult":
        return cls(
            outcome=DecisionOutcome.RESIZE, allowed=True,
            reason=reason, original_value=original, resized_value=resized,
            trace_id=trace_id,
        )

    @classmethod
    def halted(cls, reason: str, trace_id: str = "") -> "DecisionResult":
        return cls(outcome=DecisionOutcome.HALT, allowed=False, reason=reason, trace_id=trace_id)
