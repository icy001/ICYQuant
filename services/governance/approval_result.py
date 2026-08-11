"""
Approval Result — the outcome of an approval process.
"""

from __future__ import annotations

import uuid
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional


class ApprovalDecision(Enum):
    APPROVED = auto()
    REJECTED = auto()
    EXPIRED = auto()


@dataclass
class ApprovalResult:
    """The result of an approval workflow evaluation."""

    approval_id: str = field(default_factory=lambda: f"APR-{uuid.uuid4().hex[:12]}")

    # Link
    approval_request_id: str = ""
    decision_request_id: str = ""

    # Decision
    decision: ApprovalDecision = ApprovalDecision.REJECTED
    reason: str = ""
    level: str = "INTERNAL"

    # Detail
    steps_completed: List[str] = field(default_factory=list)
    approver: str = ""
    conditions: Dict[str, Any] = field(default_factory=dict)

    # Timing
    created_at: float = field(default_factory=time.time)
    resolved_at: float = field(default_factory=time.time)

    @property
    def is_approved(self) -> bool:
        return self.decision == ApprovalDecision.APPROVED

    @classmethod
    def approved(cls, approval_request_id: str, decision_request_id: str = "",
                 reason: str = "", level: str = "INTERNAL", **kwargs) -> "ApprovalResult":
        return cls(
            approval_request_id=approval_request_id,
            decision_request_id=decision_request_id,
            decision=ApprovalDecision.APPROVED,
            reason=reason,
            level=level,
            **kwargs,
        )

    @classmethod
    def rejected(cls, approval_request_id: str, decision_request_id: str = "",
                 reason: str = "", **kwargs) -> "ApprovalResult":
        return cls(
            approval_request_id=approval_request_id,
            decision_request_id=decision_request_id,
            decision=ApprovalDecision.REJECTED,
            reason=reason,
            **kwargs,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "approval_id": self.approval_id,
            "approval_request_id": self.approval_request_id,
            "decision_request_id": self.decision_request_id,
            "decision": self.decision.name,
            "reason": self.reason,
            "level": self.level,
            "steps_completed": self.steps_completed,
            "approver": self.approver,
            "conditions": self.conditions,
            "created_at": self.created_at,
            "resolved_at": self.resolved_at,
            "is_approved": self.is_approved,
        }
