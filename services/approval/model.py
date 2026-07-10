"""
Approval domain models.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from uuid import UUID


class ApprovalStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


@dataclass(
    frozen=True,
)
class ApprovalRequest:
    __slots__ = (
        "request_id",
        "action",
        "payload",
        "reason",
        "status",
        "created_at",
    )

    request_id: UUID
    action: str
    payload: dict
    reason: str
    status: ApprovalStatus
    created_at: datetime