"""
Rotation approval workflow.

Provides configurable approval modes
for rotation operations, supporting
automatic, single approval, dual approval,
and emergency override scenarios.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from ..credentials import ApprovalMode

logger = logging.getLogger(__name__)


class ApprovalStatus(str, Enum):
    """Approval request status."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    EMERGENCY_APPROVED = "emergency_approved"


@dataclass
class ApprovalRequest:
    """
    Rotation approval request.

    Represents a single approval workflow
    for a rotation operation, tracking
    approvers, decisions, and timestamps.

    Attributes:
        request_id: Unique request identifier.
        secret_key: Target secret key.
        requester: Who requested the rotation.
        reason: Justification for rotation.
        mode: Required approval mode.
        approvers: List of required approvers.
        decisions: Approval decisions recorded.
        status: Current approval status.
        created_at: When the request was created.
        expires_at: When the request expires.
        emergency: Whether this is an emergency request.
    """

    request_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    secret_key: str = ""
    requester: str = "system"
    reason: str = ""
    mode: ApprovalMode = ApprovalMode.SINGLE
    approvers: List[str] = field(default_factory=list)
    decisions: Dict[str, ApprovalStatus] = field(default_factory=dict)
    status: ApprovalStatus = ApprovalStatus.PENDING
    created_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    emergency: bool = False

    @property
    def is_approved(self) -> bool:
        """Check if the request is approved."""
        if self.status == ApprovalStatus.APPROVED:
            return True
        if self.status == ApprovalStatus.EMERGENCY_APPROVED:
            return True
        return False

    @property
    def is_expired(self) -> bool:
        """Check if the request has expired."""
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at

    @property
    def approvals_count(self) -> int:
        """Count of positive approvals."""
        return sum(
            1 for s in self.decisions.values()
            if s in (ApprovalStatus.APPROVED, ApprovalStatus.EMERGENCY_APPROVED)
        )

    @property
    def rejections_count(self) -> int:
        """Count of rejections."""
        return sum(
            1 for s in self.decisions.values()
            if s == ApprovalStatus.REJECTED
        )

    def approve(
        self,
        approver: str,
        emergency: bool = False,
    ) -> ApprovalStatus:
        """
        Record an approval decision.

        Args:
            approver: Approver identifier.
            emergency: Whether this is an emergency approval.

        Returns:
            New approval status.
        """
        if self.status != ApprovalStatus.PENDING:
            logger.warning(
                "Cannot approve request %s in state %s",
                self.request_id, self.status.value,
            )
            return self.status

        if self.is_expired:
            self.status = ApprovalStatus.EXPIRED
            return self.status

        status = (
            ApprovalStatus.EMERGENCY_APPROVED
            if emergency
            else ApprovalStatus.APPROVED
        )
        self.decisions[approver] = status

        # Check if enough approvals
        required = self._required_approvals()
        if self.approvals_count >= required:
            self.status = status
            logger.info(
                "Approval request %s approved by %s",
                self.request_id, approver,
            )

        if self.rejections_count > 0 and self.mode == ApprovalMode.SINGLE:
            self.status = ApprovalStatus.REJECTED

        return self.status

    def reject(
        self,
        approver: str,
    ) -> ApprovalStatus:
        """
        Record a rejection.

        Args:
            approver: Approver identifier.

        Returns:
            New approval status.
        """
        self.decisions[approver] = ApprovalStatus.REJECTED
        if self.mode == ApprovalMode.SINGLE or self.rejections_count > 0:
            self.status = ApprovalStatus.REJECTED
        return self.status

    def _required_approvals(self) -> int:
        """Calculate number of required approvals."""
        if self.mode == ApprovalMode.NONE:
            return 0
        elif self.mode == ApprovalMode.SINGLE:
            return 1
        elif self.mode == ApprovalMode.DUAL:
            return 2
        elif self.mode == ApprovalMode.EMERGENCY:
            return 1
        return 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "secret_key": self.secret_key,
            "requester": self.requester,
            "reason": self.reason,
            "mode": self.mode.value,
            "status": self.status.value,
            "approvals_count": self.approvals_count,
            "rejections_count": self.rejections_count,
            "is_approved": self.is_approved,
            "is_expired": self.is_expired,
            "created_at": self.created_at.isoformat() + "Z",
            "expires_at": (
                self.expires_at.isoformat() + "Z"
                if self.expires_at
                else None
            ),
            "emergency": self.emergency,
        }


@dataclass
class ApprovalResult:
    """
    Result of an approval check.

    Attributes:
        approved: Whether the rotation is approved.
        request_id: Associated request ID.
        status: Final approval status.
        approvals_count: Number of approvals received.
        message: Human-readable summary.
    """

    approved: bool = False
    request_id: str = ""
    status: ApprovalStatus = ApprovalStatus.PENDING
    approvals_count: int = 0
    message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "approved": self.approved,
            "request_id": self.request_id,
            "status": self.status.value,
            "approvals_count": self.approvals_count,
            "message": self.message,
        }


class RotationApproval:
    """
    Approval workflow manager.

    Handles creation, tracking, and
    resolution of approval requests
    for rotation operations.

    Usage:
        approval = RotationApproval()
        request = approval.request_approval(
            secret_key="database/password",
            mode=ApprovalMode.SINGLE,
        )
        result = await approval.wait_for_approval(request.request_id)
    """

    REQUEST_TIMEOUT_HOURS = 24

    def __init__(
        self,
        approvers: Optional[List[str]] = None,
        on_approved: Optional[Callable] = None,
        on_rejected: Optional[Callable] = None,
    ) -> None:
        """
        Initialize approval manager.

        Args:
            approvers: List of authorized approvers.
            on_approved: Callback for approved requests.
            on_rejected: Callback for rejected requests.
        """
        self._approvers = approvers or ["admin"]
        self._on_approved = on_approved
        self._on_rejected = on_rejected
        self._requests: Dict[str, ApprovalRequest] = {}

    def request_approval(
        self,
        secret_key: str,
        mode: ApprovalMode = ApprovalMode.SINGLE,
        requester: str = "system",
        reason: str = "",
        emergency: bool = False,
        custom_approvers: Optional[List[str]] = None,
        timeout_hours: Optional[int] = None,
    ) -> ApprovalRequest:
        """
        Create a new approval request.

        Args:
            secret_key: Target secret key.
            mode: Required approval mode.
            requester: Who requested.
            reason: Justification.
            emergency: Whether this is an emergency.
            custom_approvers: Specific approvers for this request.
            timeout_hours: Request timeout in hours.

        Returns:
            Created ApprovalRequest.
        """
        approvers = custom_approvers or self._approvers
        timeout = timeout_hours or self.REQUEST_TIMEOUT_HOURS

        request = ApprovalRequest(
            secret_key=secret_key,
            requester=requester,
            reason=reason,
            mode=mode,
            approvers=approvers,
            emergency=emergency,
            expires_at=datetime.utcnow() + timedelta(hours=timeout),
        )

        # Auto-approve for NONE mode
        if mode == ApprovalMode.NONE:
            request.status = ApprovalStatus.APPROVED
            request.decisions["auto"] = ApprovalStatus.APPROVED

        self._requests[request.request_id] = request
        logger.info(
            "Approval request created: %s (mode=%s, emergency=%s)",
            request.request_id, mode.value, emergency,
        )

        return request

    def approve_request(
        self,
        request_id: str,
        approver: str,
        emergency: bool = False,
    ) -> ApprovalResult:
        """
        Approve a pending request.

        Args:
            request_id: Request to approve.
            approver: Who approves.
            emergency: Emergency approval flag.

        Returns:
            ApprovalResult.
        """
        request = self._requests.get(request_id)
        if request is None:
            return ApprovalResult(
                approved=False,
                request_id=request_id,
                status=ApprovalStatus.PENDING,
                message="Request not found",
            )

        new_status = request.approve(approver, emergency=emergency)

        if request.is_approved and self._on_approved:
            try:
                self._on_approved(request)
            except Exception as e:
                logger.error("Approval callback error: %s", e)

        return ApprovalResult(
            approved=request.is_approved,
            request_id=request_id,
            status=new_status,
            approvals_count=request.approvals_count,
            message=f"Approval {'approved' if request.is_approved else 'pending'}",
        )

    def reject_request(
        self,
        request_id: str,
        approver: str,
    ) -> ApprovalResult:
        """
        Reject a pending request.

        Args:
            request_id: Request to reject.
            approver: Who rejects.

        Returns:
            ApprovalResult.
        """
        request = self._requests.get(request_id)
        if request is None:
            return ApprovalResult(
                approved=False,
                request_id=request_id,
                status=ApprovalStatus.PENDING,
                message="Request not found",
            )

        new_status = request.reject(approver)

        if new_status == ApprovalStatus.REJECTED and self._on_rejected:
            try:
                self._on_rejected(request)
            except Exception as e:
                logger.error("Rejection callback error: %s", e)

        return ApprovalResult(
            approved=False,
            request_id=request_id,
            status=new_status,
            approvals_count=request.approvals_count,
            message="Approval rejected",
        )

    def get_request(
        self,
        request_id: str,
    ) -> Optional[ApprovalRequest]:
        """Get an approval request by ID."""
        return self._requests.get(request_id)

    def check_approval(
        self,
        request_id: str,
    ) -> ApprovalResult:
        """
        Check if a request is approved.

        Args:
            request_id: Request ID to check.

        Returns:
            ApprovalResult.
        """
        request = self._requests.get(request_id)
        if request is None:
            return ApprovalResult(
                approved=False,
                request_id=request_id,
                message="Request not found",
            )

        if request.is_expired:
            request.status = ApprovalStatus.EXPIRED
            return ApprovalResult(
                approved=False,
                request_id=request_id,
                status=ApprovalStatus.EXPIRED,
                message="Request expired",
            )

        return ApprovalResult(
            approved=request.is_approved,
            request_id=request_id,
            status=request.status,
            approvals_count=request.approvals_count,
            message=f"Request is {request.status.value}",
        )

    def cleanup_expired(self) -> int:
        """
        Remove expired requests.

        Returns:
            Number of expired requests removed.
        """
        expired = [
            rid for rid, req in self._requests.items()
            if req.is_expired and not req.is_approved
        ]
        for rid in expired:
            del self._requests[rid]
        return len(expired)

    def list_requests(
        self,
        status: Optional[ApprovalStatus] = None,
    ) -> List[Dict[str, Any]]:
        """List approval requests."""
        requests = list(self._requests.values())
        if status:
            requests = [r for r in requests if r.status == status]
        return [r.to_dict() for r in requests]

    def get_stats(self) -> Dict[str, Any]:
        """Get approval statistics."""
        total = len(self._requests)
        by_status: Dict[str, int] = {}
        for req in self._requests.values():
            s = req.status.value
            by_status[s] = by_status.get(s, 0) + 1

        return {
            "total_requests": total,
            "by_status": by_status,
            "approver_count": len(self._approvers),
            "expired_removed": self.cleanup_expired(),
        }
