"""
Approval Response — the outcome of an approval request.

This is what the Approval Engine returns to the caller after processing
a request through the workflow, including whether it was approved, by whom,
and any conditions applied.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .approval_status import ApprovalStatus
from .approval_scope import ApprovalScope


@dataclass
class ApprovalResponse:
    """Structured response from the approval pipeline."""

    approval_id: str
    request_id: str
    decision_id: str

    # Status
    status: ApprovalStatus = ApprovalStatus.PENDING
    approved: bool = False

    # Who approved
    approvers: List[ApproverEntry] = field(default_factory=list)

    # Conditions
    conditions: Dict[str, Any] = field(default_factory=dict)

    # Binding — what was approved
    approved_scope: Optional[ApprovalScope] = None
    approved_amount: Optional[float] = None
    approved_action: str = ""

    # Validity
    valid_from: float = 0.0
    valid_until: float = 0.0
    consumed: bool = False

    # Approval lineage
    policy_version: str = ""
    authority_id: str = ""
    delegation_id: str = ""

    # Reason
    reason: str = ""
    reject_reason: str = ""

    # Meta
    created_at: float = 0.0
    updated_at: float = 0.0
    executed_at: Optional[float] = None

    def is_valid(self, current_time: Optional[float] = None) -> bool:
        """Check if the approval is still valid (not expired, not consumed)."""
        import time
        now = current_time or time.time()
        if self.consumed:
            return False
        if self.valid_until > 0 and now > self.valid_until:
            return False
        if self.status != ApprovalStatus.APPROVED:
            return False
        return True

    def consume(self) -> bool:
        """Consume the approval (single-use, replay protection)."""
        if self.consumed:
            return False
        if self.status != ApprovalStatus.APPROVED:
            return False
        self.consumed = True
        self.status = ApprovalStatus.EXECUTED
        return True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "approval_id": self.approval_id,
            "request_id": self.request_id,
            "decision_id": self.decision_id,
            "status": self.status.name,
            "approved": self.approved,
            "approvers": [a.to_dict() for a in self.approvers],
            "conditions": self.conditions,
            "approved_scope": self.approved_scope.to_dict() if self.approved_scope else None,
            "approved_amount": self.approved_amount,
            "approved_action": self.approved_action,
            "valid_from": self.valid_from,
            "valid_until": self.valid_until,
            "consumed": self.consumed,
            "policy_version": self.policy_version,
            "authority_id": self.authority_id,
            "delegation_id": self.delegation_id,
            "reason": self.reason,
            "reject_reason": self.reject_reason,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "executed_at": self.executed_at,
        }


@dataclass
class ApproverEntry:
    """Record of a single approver's action."""

    approver_id: str
    approver_name: str = ""
    action: str = ""  # APPROVE / REJECT / ABSTAIN
    role: str = ""
    authority_id: str = ""
    delegation_id: str = ""
    comment: str = ""
    timestamp: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "approver_id": self.approver_id,
            "approver_name": self.approver_name,
            "action": self.action,
            "role": self.role,
            "authority_id": self.authority_id,
            "delegation_id": self.delegation_id,
            "comment": self.comment,
            "timestamp": self.timestamp,
        }
