"""
Approval Request — a single request for approval.
"""

from __future__ import annotations

import uuid
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, Optional


class ApprovalRequestStatus(Enum):
    PENDING = auto()
    APPROVED = auto()
    REJECTED = auto()
    EXPIRED = auto()
    CANCELLED = auto()


@dataclass
class ApprovalRequest:
    """A formal request for approval within the governance pipeline."""

    request_id: str = field(default_factory=lambda: f"APR-{uuid.uuid4().hex[:12]}")

    # Link back
    decision_request_id: str = ""
    decision_type: str = ""

    # What is being approved
    amount: Optional[float] = None
    risk: Optional[float] = None
    leverage: Optional[float] = None

    # Approval level
    level: str = "INTERNAL"   # From ApprovalLevel

    # Context
    context: Dict[str, Any] = field(default_factory=dict)
    reason: str = ""

    # Status
    status: ApprovalRequestStatus = ApprovalRequestStatus.PENDING

    # Timing
    created_at: float = field(default_factory=time.time)
    expires_at: Optional[float] = None
    resolved_at: Optional[float] = None

    # Resolver
    resolved_by: str = ""
    resolution_reason: str = ""

    @property
    def is_pending(self) -> bool:
        return self.status == ApprovalRequestStatus.PENDING

    @property
    def is_resolved(self) -> bool:
        return self.status in (ApprovalRequestStatus.APPROVED, ApprovalRequestStatus.REJECTED)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "decision_request_id": self.decision_request_id,
            "decision_type": self.decision_type,
            "amount": self.amount,
            "risk": self.risk,
            "leverage": self.leverage,
            "level": self.level,
            "context": self.context,
            "reason": self.reason,
            "status": self.status.name,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "resolved_at": self.resolved_at,
            "resolved_by": self.resolved_by,
            "resolution_reason": self.resolution_reason,
        }
