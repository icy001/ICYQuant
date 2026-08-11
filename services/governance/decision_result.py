"""
Decision Result — final output from governance evaluation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, Optional


class DecisionOutcome(Enum):
    """Final outcome of a governance decision."""

    ALLOWED = auto()
    REVIEW_REQUIRED = auto()
    REJECTED = auto()
    BLOCKED = auto()
    OVERRIDDEN = auto()
    EXPIRED = auto()
    CANCELLED = auto()
    ERROR = auto()


@dataclass
class DecisionResult:
    """Final result returned to the caller after governance evaluation."""

    request_id: str
    decision_id: Optional[str] = None
    outcome: DecisionOutcome = DecisionOutcome.REJECTED
    reason: str = ""
    allowed_amount: Optional[float] = None
    audit_record: Optional[Any] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_allowed(self) -> bool:
        return self.outcome in (DecisionOutcome.ALLOWED, DecisionOutcome.OVERRIDDEN)

    @property
    def is_rejected(self) -> bool:
        return not self.is_allowed

    @property
    def requires_review(self) -> bool:
        return self.outcome == DecisionOutcome.REVIEW_REQUIRED

    @classmethod
    def allowed(cls, request_id: str, reason: str = "",
                decision_id: Optional[str] = None, **kwargs) -> "DecisionResult":
        return cls(
            request_id=request_id,
            decision_id=decision_id,
            outcome=DecisionOutcome.ALLOWED,
            reason=reason,
            **kwargs,
        )

    @classmethod
    def rejected(cls, request_id: str, reason: str = "",
                 decision_id: Optional[str] = None, **kwargs) -> "DecisionResult":
        return cls(
            request_id=request_id,
            decision_id=decision_id,
            outcome=DecisionOutcome.REJECTED,
            reason=reason,
            **kwargs,
        )

    @classmethod
    def review(cls, request_id: str, reason: str = "",
               decision_id: Optional[str] = None, **kwargs) -> "DecisionResult":
        return cls(
            request_id=request_id,
            decision_id=decision_id,
            outcome=DecisionOutcome.REVIEW_REQUIRED,
            reason=reason,
            **kwargs,
        )

    @classmethod
    def blocked(cls, request_id: str, reason: str = "",
                decision_id: Optional[str] = None, **kwargs) -> "DecisionResult":
        return cls(
            request_id=request_id,
            decision_id=decision_id,
            outcome=DecisionOutcome.BLOCKED,
            reason=reason,
            **kwargs,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "decision_id": self.decision_id,
            "outcome": self.outcome.name,
            "reason": self.reason,
            "allowed_amount": self.allowed_amount,
            "is_allowed": self.is_allowed,
            "metadata": self.metadata,
        }
