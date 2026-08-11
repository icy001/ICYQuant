"""
Approval Workflow — Manual and automated approval routing for risk decisions.

Handles the lifecycle of pending approvals: request, approve, reject,
expire, and override. Integrates with the approval policy engine to
route decisions to the appropriate approver pool.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

from .risk_decision import RiskDecision, Decision
from .approval_policy import ApprovalPolicy, ApprovalAction

logger = logging.getLogger(__name__)


class ApprovalStatus(str, Enum):
    """Status of an approval request."""
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    OVERRIDDEN = "OVERRIDDEN"
    CANCELLED = "CANCELLED"


@dataclass
class ApprovalRequest:
    """A single approval request tracked in the workflow."""
    approval_id: str = field(default_factory=lambda: uuid4().hex)
    decision_id: str = ""
    request_id: str = ""
    status: ApprovalStatus = ApprovalStatus.PENDING
    risk_score: float = 0.0
    action: ApprovalAction = ApprovalAction.ROUTE_TO_APPROVER
    approver_pool: list[str] = field(default_factory=list)
    assigned_approver: Optional[str] = None
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    rejected_by: Optional[str] = None
    rejected_at: Optional[datetime] = None
    rejection_reason: str = ""
    expires_at: Optional[datetime] = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class ApprovalWorkflow:
    """
    Approval workflow engine for pre-trade risk decisions.

    Manages the lifecycle of manual approval requests and provides
    integration with the approval policy engine for automatic routing.

    Usage::

        workflow = ApprovalWorkflow(policy=ApprovalPolicy())
        pending = await workflow.submit(risk_decision)
        result = await workflow.approve(pending.approval_id, "admin-01")
    """

    def __init__(
        self,
        policy: Optional[ApprovalPolicy] = None,
        approval_timeout: int = 300,
    ) -> None:
        self._policy = policy or ApprovalPolicy()
        self._approval_timeout = approval_timeout
        self._pending: dict[str, ApprovalRequest] = {}
        self._history: dict[str, ApprovalRequest] = {}
        self._lock = asyncio.Lock()

    # ---- Submission ----

    async def submit(
        self,
        decision: RiskDecision,
        action: Optional[ApprovalAction] = None,
    ) -> Optional[ApprovalRequest]:
        """
        Submit a risk decision for approval routing.

        Only non-auto decisions go through this workflow. Auto-approved
        and auto-rejected decisions bypass it entirely.
        """
        if action is None:
            action = ApprovalAction.ROUTE_TO_APPROVER

        if action in (ApprovalAction.AUTO_APPROVE, ApprovalAction.AUTO_REJECT):
            return None  # No workflow needed

        request = ApprovalRequest(
            decision_id=decision.decision_id,
            request_id=decision.request_id,
            risk_score=decision.risk_score,
            action=action,
            approver_pool=list(self._policy.approver_pool),
            expires_at=datetime.now(timezone.utc) + timedelta(
                seconds=self._approval_timeout
            ),
        )

        async with self._lock:
            self._pending[request.approval_id] = request

        logger.info(
            f"Approval submitted: {request.approval_id} "
            f"(score={request.risk_score:.1f}, action={action.value})"
        )
        return request

    # ---- Approval Actions ----

    async def approve(self, approval_id: str, approver: str) -> Optional[RiskDecision]:
        """Approve a pending approval request."""
        async with self._lock:
            request = self._pending.get(approval_id)
            if not request:
                logger.warning(f"Approval not found: {approval_id}")
                return None

            if request.status != ApprovalStatus.PENDING:
                logger.warning(f"Approval {approval_id} already resolved: {request.status.value}")
                return None

            request.status = ApprovalStatus.APPROVED
            request.approved_by = approver
            request.approved_at = datetime.now(timezone.utc)
            self._history[approval_id] = request
            del self._pending[approval_id]

        logger.info(f"Approval {approval_id} approved by {approver}.")
        return self._build_decision_from_approval(request)

    async def reject(
        self, approval_id: str, approver: str, reason: str = ""
    ) -> Optional[RiskDecision]:
        """Reject a pending approval request."""
        async with self._lock:
            request = self._pending.get(approval_id)
            if not request:
                logger.warning(f"Approval not found: {approval_id}")
                return None

            if request.status != ApprovalStatus.PENDING:
                logger.warning(f"Approval {approval_id} already resolved: {request.status.value}")
                return None

            request.status = ApprovalStatus.REJECTED
            request.rejected_by = approver
            request.rejected_at = datetime.now(timezone.utc)
            request.rejection_reason = reason
            self._history[approval_id] = request
            del self._pending[approval_id]

        logger.info(f"Approval {approval_id} rejected by {approver}: {reason}")
        return self._build_decision_from_approval(request)

    async def cancel(self, approval_id: str) -> bool:
        """Cancel a pending approval request."""
        async with self._lock:
            request = self._pending.get(approval_id)
            if not request:
                return False
            request.status = ApprovalStatus.CANCELLED
            self._history[approval_id] = request
            del self._pending[approval_id]
        logger.info(f"Approval {approval_id} cancelled.")
        return True

    # ---- Expiration ----

    async def check_expirations(self) -> list[str]:
        """Check for expired approvals and expire them. Returns expired IDs."""
        now = datetime.now(timezone.utc)
        expired_ids: list[str] = []

        async with self._lock:
            for approval_id, request in list(self._pending.items()):
                if request.expires_at and request.expires_at < now:
                    request.status = ApprovalStatus.EXPIRED
                    self._history[approval_id] = request
                    del self._pending[approval_id]
                    expired_ids.append(approval_id)

        if expired_ids:
            logger.warning(f"Expired approvals: {expired_ids}")
        return expired_ids

    # ---- Query ----

    async def get_pending(self) -> list[ApprovalRequest]:
        """Get all pending approval requests."""
        async with self._lock:
            return list(self._pending.values())

    async def get_request(self, approval_id: str) -> Optional[ApprovalRequest]:
        """Get a specific approval request by ID."""
        async with self._lock:
            return self._pending.get(approval_id) or self._history.get(approval_id)

    async def get_history(self, limit: int = 100) -> list[ApprovalRequest]:
        """Get approval history (most recent first)."""
        async with self._lock:
            items = list(self._history.values())
            items.sort(key=lambda r: r.created_at, reverse=True)
            return items[:limit]

    # ---- Internal ----

    def _build_decision_from_approval(
        self, request: ApprovalRequest
    ) -> RiskDecision:
        """Build a RiskDecision from an approved/rejected approval."""
        if request.status == ApprovalStatus.APPROVED:
            return RiskDecision.approved(
                request_id=request.request_id,
                approver=request.approved_by,
                approved_at=request.approved_at,
            )
        return RiskDecision.rejected(
            request_id=request.request_id,
            reasons=[{"message": request.rejection_reason or "Manually rejected."}],
        )
