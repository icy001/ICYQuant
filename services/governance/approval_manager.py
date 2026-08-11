"""
Approval Manager — orchestrates the approval lifecycle.

Manages creation, submission, review, and resolution of approval requests.
Sits between the existing ApprovalEngine (pure logic) and ApprovalRepository (storage),
adding lifecycle management, timeout handling, and batch operations.

Works with the existing ApprovalRequest model (uses request_id as primary key,
ApprovalRequestStatus for status).
"""

from __future__ import annotations

import time
import uuid
from typing import List, Optional

from .approval_request import ApprovalRequest, ApprovalRequestStatus
from .approval_response import ApprovalResponse
from .approval_status import ApprovalStatus
from .approval_transition import ApprovalTransition
from .approval_repository import ApprovalRepository


class ApprovalManager:
    """
    Manages the full approval lifecycle:

      PENDING → APPROVED/REJECTED → EXECUTED

    This is an extended manager on top of the existing ApprovalEngine,
    providing richer lifecycle control.
    """

    def __init__(self, repository: Optional[ApprovalRepository] = None):
        self._repo = repository or ApprovalRepository()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def create_request(
        self,
        decision_request_id: str = "",
        decision_type: str = "",
        amount: float = 0.0,
        risk: float = 0.0,
        level: str = "INTERNAL",
        reason: str = "",
        ttl_seconds: float = 3600.0,
        **context,
    ) -> ApprovalRequest:
        """
        Create a new approval request in PENDING status.

        Maps to existing ApprovalRequest fields:
          - request_id (auto-generated)
          - decision_request_id
          - decision_type
          - amount / risk
          - level
          - reason
        """
        now = time.time()
        request = ApprovalRequest(
            request_id=f"APR-{int(now * 1_000_000)}-{uuid.uuid4().hex[:6]}",
            decision_request_id=decision_request_id,
            decision_type=decision_type,
            amount=amount,
            risk=risk,
            level=level,
            reason=reason,
            context=context,
            status=ApprovalRequestStatus.PENDING,
            expires_at=now + ttl_seconds,
            created_at=now,
        )

        self._repo.save_request(request)
        return request

    def approve(self, request: ApprovalRequest, resolved_by: str,
                resolution_reason: str = "") -> ApprovalResponse:
        """
        Approve a pending request.

        Returns an ApprovalResponse that binds the decision to the approval.
        """
        if request.status != ApprovalRequestStatus.PENDING:
            raise ValueError(
                f"Cannot approve request {request.request_id}: "
                f"status is {request.status.name}"
            )

        request.status = ApprovalRequestStatus.APPROVED
        request.resolved_by = resolved_by
        request.resolved_at = time.time()
        request.resolution_reason = resolution_reason

        now = time.time()
        response = ApprovalResponse(
            approval_id=request.request_id,
            request_id=request.request_id,
            decision_id=request.decision_request_id,
            status=ApprovalStatus.APPROVED,
            approved=True,
            approved_amount=request.amount,
            approved_action=request.decision_type,
            valid_from=now,
            valid_until=request.expires_at or (now + 3600),
            reason=resolution_reason,
            created_at=now,
            updated_at=now,
        )

        self._repo.save_request(request)
        self._repo.save_response(request.request_id, response)
        return response

    def reject(self, request: ApprovalRequest, resolved_by: str,
               reason: str = "") -> ApprovalResponse:
        """Reject a pending request."""
        if request.status != ApprovalRequestStatus.PENDING:
            raise ValueError(
                f"Cannot reject request {request.request_id}: "
                f"status is {request.status.name}"
            )

        request.status = ApprovalRequestStatus.REJECTED
        request.resolved_by = resolved_by
        request.resolved_at = time.time()
        request.resolution_reason = reason

        now = time.time()
        response = ApprovalResponse(
            approval_id=request.request_id,
            request_id=request.request_id,
            decision_id=request.decision_request_id,
            status=ApprovalStatus.REJECTED,
            approved=False,
            reject_reason=reason,
            created_at=now,
            updated_at=now,
        )

        self._repo.save_request(request)
        self._repo.save_response(request.request_id, response)
        return response

    def cancel(self, request: ApprovalRequest, resolved_by: str,
               reason: str = "") -> ApprovalRequest:
        """Cancel a pending request (before execution)."""
        if request.status in (ApprovalRequestStatus.APPROVED,):
            request.status = ApprovalRequestStatus.CANCELLED
            request.resolved_by = resolved_by
            request.resolved_at = time.time()
            request.resolution_reason = reason
            self._repo.save_request(request)
            return request
        if request.status == ApprovalRequestStatus.PENDING:
            request.status = ApprovalRequestStatus.CANCELLED
            request.resolved_by = resolved_by
            request.resolved_at = time.time()
            request.resolution_reason = reason
            self._repo.save_request(request)
            return request
        raise ValueError(
            f"Cannot cancel request {request.request_id}: "
            f"status is {request.status.name}"
        )

    def expire(self, request: ApprovalRequest) -> ApprovalRequest:
        """Mark a request as expired (e.g., timeout)."""
        if request.status not in (ApprovalRequestStatus.PENDING,):
            raise ValueError(f"Cannot expire request {request.request_id}: status={request.status.name}")
        request.status = ApprovalRequestStatus.EXPIRED
        request.resolved_at = time.time()
        self._repo.save_request(request)
        return request

    def mark_executed(self, request: ApprovalRequest, response: ApprovalResponse) -> ApprovalResponse:
        """Mark APPROVED → EXECUTED (single-use, replay protected)."""
        if not response.consume():
            raise ValueError(f"Cannot execute approval {request.request_id}: already consumed")

        response.status = ApprovalStatus.EXECUTED
        response.executed_at = time.time()
        response.updated_at = time.time()

        self._repo.save_request(request)
        self._repo.save_response(request.request_id, response)
        return response

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_request(self, request_id: str) -> Optional[ApprovalRequest]:
        """Get an approval request by ID."""
        return self._repo.load_request(request_id)

    def get_response(self, request_id: str) -> Optional[ApprovalResponse]:
        """Get an approval response by request ID."""
        return self._repo.load_response(request_id)

    def list_pending(self) -> List[ApprovalRequest]:
        """List all pending approval requests."""
        return self._repo.list_requests(ApprovalRequestStatus.PENDING)

    def list_approved(self) -> List[ApprovalRequest]:
        """List all approved requests."""
        return self._repo.list_requests(ApprovalRequestStatus.APPROVED)

    # ------------------------------------------------------------------
    # Expiry check
    # ------------------------------------------------------------------

    def expire_all_overdue(self) -> int:
        """Expire all overdue pending requests. Returns count expired."""
        count = 0
        for req in self._repo.list_requests(ApprovalRequestStatus.PENDING):
            if req.expires_at is not None and time.time() > req.expires_at:
                req.status = ApprovalRequestStatus.EXPIRED
                req.resolved_at = time.time()
                self._repo.save_request(req)
                count += 1
        return count
