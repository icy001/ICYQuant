"""
ICYQuant Collaboration — approval workflow for research outputs.

Manages the multi-stage approval process for research reports before
publication, with configurable approval chains and status tracking.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class ApprovalStep(str, Enum):
    AUTHOR_REVIEW = "author_review"
    PEER_REVIEW = "peer_review"
    LEAD_REVIEW = "lead_review"
    COMPLIANCE = "compliance"
    FINAL = "final"


@dataclass
class ApprovalStepResult:
    """Result of a single approval step."""
    step: ApprovalStep
    reviewer_id: str
    status: ApprovalStatus = ApprovalStatus.PENDING
    comment: str = ""
    reviewed_at: Optional[datetime] = None


@dataclass
class ApprovalRequest:
    """An approval workflow request."""
    request_id: str
    target_type: str
    target_id: str
    requester_id: str
    status: ApprovalStatus = ApprovalStatus.PENDING
    steps: list[ApprovalStepResult] = field(default_factory=list)
    current_step_index: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    metadata: dict[str, Any] = field(default_factory=dict)


class ApprovalWorkflow:
    """Multi-stage approval workflow for research outputs.

    Default workflow:
        Author Review → Peer Review → Lead Review → Compliance → Final

    Supports:
        - Configurable approval chains
        - Sequential step execution
        - Comments at each step
        - Cancellation and rejection
    """

    DEFAULT_STEPS = [
        ApprovalStep.AUTHOR_REVIEW,
        ApprovalStep.PEER_REVIEW,
        ApprovalStep.LEAD_REVIEW,
        ApprovalStep.COMPLIANCE,
        ApprovalStep.FINAL,
    ]

    def __init__(self) -> None:
        self._requests: dict[str, ApprovalRequest] = {}
        self._total_created = 0

    def create_request(
        self,
        target_type: str,
        target_id: str,
        requester_id: str,
        steps: Optional[list[ApprovalStep]] = None,
    ) -> ApprovalRequest:
        """Create a new approval request."""
        import uuid

        workflow_steps = steps or self.DEFAULT_STEPS
        step_results = [ApprovalStepResult(step=s, reviewer_id="") for s in workflow_steps]

        request = ApprovalRequest(
            request_id=str(uuid.uuid4()),
            target_type=target_type,
            target_id=target_id,
            requester_id=requester_id,
            steps=step_results,
        )
        self._requests[request.request_id] = request
        self._total_created += 1
        logger.info("Created approval request: %s", request.request_id)
        return request

    def assign_step(
        self,
        request_id: str,
        step: ApprovalStep,
        reviewer_id: str,
    ) -> bool:
        """Assign a reviewer to a specific step."""
        request = self._requests.get(request_id)
        if request is None:
            return False

        for s in request.steps:
            if s.step == step:
                s.reviewer_id = reviewer_id
                return True
        return False

    def approve_step(
        self,
        request_id: str,
        step: ApprovalStep,
        reviewer_id: str,
        comment: str = "",
    ) -> bool:
        """Approve a specific step in the workflow."""
        request = self._requests.get(request_id)
        if request is None:
            return False

        for i, s in enumerate(request.steps):
            if s.step == step and s.status == ApprovalStatus.PENDING:
                s.status = ApprovalStatus.APPROVED
                s.reviewer_id = reviewer_id
                s.comment = comment
                s.reviewed_at = datetime.now(timezone.utc)

                # Advance to next step
                request.current_step_index = i + 1

                # Check if all steps are approved
                if all(s2.status == ApprovalStatus.APPROVED for s2 in request.steps):
                    request.status = ApprovalStatus.APPROVED
                    request.completed_at = datetime.now(timezone.utc)
                    logger.info("Approval request %s fully approved", request_id)

                return True
        return False

    def reject_step(
        self,
        request_id: str,
        step: ApprovalStep,
        reviewer_id: str,
        reason: str,
    ) -> bool:
        """Reject a specific step."""
        request = self._requests.get(request_id)
        if request is None:
            return False

        for s in request.steps:
            if s.step == step:
                s.status = ApprovalStatus.REJECTED
                s.reviewer_id = reviewer_id
                s.comment = reason
                s.reviewed_at = datetime.now(timezone.utc)
                request.status = ApprovalStatus.REJECTED
                request.completed_at = datetime.now(timezone.utc)
                return True
        return False

    def cancel(self, request_id: str) -> bool:
        """Cancel an approval request."""
        request = self._requests.get(request_id)
        if request is None:
            return False
        request.status = ApprovalStatus.CANCELLED
        request.completed_at = datetime.now(timezone.utc)
        return True

    def get_request(self, request_id: str) -> Optional[ApprovalRequest]:
        return self._requests.get(request_id)

    def get_status(self, request_id: str) -> Optional[dict[str, Any]]:
        """Get detailed status of an approval request."""
        request = self._requests.get(request_id)
        if request is None:
            return None

        return {
            "request_id": request.request_id,
            "status": request.status.value,
            "target_type": request.target_type,
            "target_id": request.target_id,
            "current_step": request.current_step_index,
            "total_steps": len(request.steps),
            "steps": [
                {
                    "step": s.step.value,
                    "status": s.status.value,
                    "reviewer_id": s.reviewer_id,
                    "comment": s.comment,
                }
                for s in request.steps
            ],
        }

    @property
    def total_created(self) -> int:
        return self._total_created
