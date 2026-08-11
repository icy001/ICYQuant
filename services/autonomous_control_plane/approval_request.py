"""
Approval Request — Structured approval request model.

Individual approval requests with metadata, context, and lifecycle.
"""

from __future__ import annotations

import uuid
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class ApprovalRequestStatus(Enum):
    CREATED = "created"
    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


@dataclass
class ApprovalRequest:
    """
    A single approval request for an autonomous decision.
    """
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    decision_id: str = ""
    requested_by: str = "autonomous"
    action: str = ""
    scope: str = ""
    status: ApprovalRequestStatus = ApprovalRequestStatus.CREATED

    created_at: float = field(default_factory=time.time)
    expires_at: Optional[float] = None
    resolved_at: Optional[float] = None
    resolved_by: Optional[str] = None

    context: dict = field(default_factory=dict)
    reason: str = ""
    comment: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "request_id": self.request_id,
            "decision_id": self.decision_id,
            "requested_by": self.requested_by,
            "action": self.action,
            "scope": self.scope,
            "status": self.status.value,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "resolved_at": self.resolved_at,
            "resolved_by": self.resolved_by,
            "reason": self.reason,
            "comment": self.comment,
        }
