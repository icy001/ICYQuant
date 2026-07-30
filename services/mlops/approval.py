"""
Approval Workflow Manager.

Multi-stage approval workflow for model promotion:
Candidate → Risk Review → Research Approval → Production → Archive

Supports dual approval, timeouts, and audit trail.
"""

import enum
import time
import uuid
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ApprovalStage(str, enum.Enum):
    """Stages in the approval workflow."""
    SUBMITTED = "submitted"
    RISK_REVIEW = "risk_review"
    RESEARCH_REVIEW = "research_review"
    FINAL_APPROVAL = "final_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class ApprovalStatus(str, enum.Enum):
    """Status of an individual approval action."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    SKIPPED = "skipped"


class ApprovalAction(str, enum.Enum):
    """Possible actions on an approval request."""
    APPROVE = "approve"
    REJECT = "reject"
    REQUEST_CHANGES = "request_changes"
    DELEGATE = "delegate"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class ApprovalConfig:
    """Configuration for the approval workflow."""

    # Stages
    require_risk_review: bool = True
    require_research_review: bool = True
    require_dual_approval: bool = True  # Two approvers for final stage
    require_final_approval: bool = True

    # Timing
    stage_timeout_hours: float = 48.0  # Auto-reject after timeout
    request_ttl_hours: float = 168.0  # 7 days total

    # Auto-approval
    auto_approve_on_evaluation_pass: bool = False
    auto_approve_score_threshold: float = 90.0  # Score above this auto-approves

    # Notifications
    notify_on_stage_change: bool = True
    notify_on_approval: bool = True
    notify_on_rejection: bool = True


@dataclass
class ApprovalRequest:
    """A model promotion approval request."""

    request_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    model_name: str = ""
    model_version: str = ""
    requested_by: str = ""

    # Current state
    current_stage: ApprovalStage = ApprovalStage.SUBMITTED
    overall_status: ApprovalStatus = ApprovalStatus.PENDING

    # Evaluation data
    evaluation_score: float = 0.0
    evaluation_id: Optional[str] = None
    metrics_summary: Dict[str, float] = field(default_factory=dict)

    # Reason
    promotion_reason: str = ""

    # Timing
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    expires_at: float = field(default_factory=lambda: time.time() + 7 * 86400)

    # Approval history
    approvals: List[Dict[str, Any]] = field(default_factory=list)
    required_approvers: List[str] = field(default_factory=list)

    # Comments
    comments: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "model_name": self.model_name,
            "model_version": self.model_version,
            "requested_by": self.requested_by,
            "current_stage": self.current_stage.value,
            "overall_status": self.overall_status.value,
            "evaluation_score": self.evaluation_score,
            "promotion_reason": self.promotion_reason,
            "created_at": self.created_at,
            "approvals": self.approvals,
            "comments": self.comments,
        }

    @property
    def is_terminal(self) -> bool:
        return self.overall_status in (
            ApprovalStatus.APPROVED, ApprovalStatus.REJECTED,
            ApprovalStatus.EXPIRED,
        )

    @property
    def is_expired(self) -> bool:
        return time.time() > self.expires_at


# ---------------------------------------------------------------------------
# Approval Manager
# ---------------------------------------------------------------------------

class ApprovalManager:
    """Manages multi-stage approval workflow for model promotion.

    Implements:
    - Risk Review → Research Review → Final Approval pipeline
    - Dual-approver requirement for production promotion
    - Timeout-based auto-rejection
    - Full audit trail

    Usage::

        am = ApprovalManager(config)
        request = am.submit(
            model_name="Alpha_v39",
            model_version="1.0.1",
            requested_by="researcher_1",
            evaluation_score=85.0,
        )
        am.approve(request.request_id, "risk_manager", ApprovalStage.RISK_REVIEW)
        am.approve(request.request_id, "lead_researcher", ApprovalStage.RESEARCH_REVIEW)
        am.final_approve(request.request_id, ["admin_1", "admin_2"])
    """

    def __init__(self, config: ApprovalConfig):
        self.config = config
        self._requests: Dict[str, ApprovalRequest] = {}
        self._history: List[ApprovalRequest] = []
        self._on_status_change: List[Callable] = []

    # ------------------------------------------------------------------
    # Submission
    # ------------------------------------------------------------------

    def submit(
        self,
        model_name: str,
        model_version: str,
        requested_by: str,
        evaluation_score: float = 0.0,
        evaluation_id: Optional[str] = None,
        metrics_summary: Optional[Dict[str, float]] = None,
        promotion_reason: str = "",
        required_approvers: Optional[List[str]] = None,
    ) -> ApprovalRequest:
        """Submit a model for promotion approval.

        Args:
            model_name: Model to promote.
            model_version: Version to promote.
            requested_by: User requesting promotion.
            evaluation_score: Evaluation composite score.
            evaluation_id: Reference to evaluation result.
            metrics_summary: Key metrics summary.
            promotion_reason: Why promotion is requested.
            required_approvers: List of required approver usernames.

        Returns:
            The created ApprovalRequest.
        """
        request = ApprovalRequest(
            model_name=model_name,
            model_version=model_version,
            requested_by=requested_by,
            evaluation_score=evaluation_score,
            evaluation_id=evaluation_id,
            metrics_summary=metrics_summary or {},
            promotion_reason=promotion_reason,
            required_approvers=required_approvers or [],
        )

        # Auto-approve if score exceeds threshold
        if (
            self.config.auto_approve_on_evaluation_pass
            and evaluation_score >= self.config.auto_approve_score_threshold
        ):
            request.current_stage = ApprovalStage.APPROVED
            request.overall_status = ApprovalStatus.APPROVED
            logger.info(
                f"Auto-approved {model_name} v{model_version} "
                f"(score={evaluation_score} >= {self.config.auto_approve_score_threshold})"
            )
        else:
            # Start approval workflow
            stages = self._get_required_stages()
            if stages:
                request.current_stage = stages[0]

        self._requests[request.request_id] = request
        logger.info(
            f"Approval request {request.request_id} submitted: "
            f"{model_name} v{model_version} by {requested_by}"
        )

        self._notify_status_change(request)
        return request

    def _get_required_stages(self) -> List[ApprovalStage]:
        """Get the list of required approval stages based on config."""
        stages = []
        if self.config.require_risk_review:
            stages.append(ApprovalStage.RISK_REVIEW)
        if self.config.require_research_review:
            stages.append(ApprovalStage.RESEARCH_REVIEW)
        if self.config.require_final_approval:
            stages.append(ApprovalStage.FINAL_APPROVAL)
        return stages

    # ------------------------------------------------------------------
    # Approval Actions
    # ------------------------------------------------------------------

    def approve(
        self,
        request_id: str,
        approver: str,
        stage: ApprovalStage,
        comment: str = "",
    ) -> bool:
        """Approve at a specific stage.

        Args:
            request_id: Request to approve.
            approver: Username of the approver.
            stage: Which stage is being approved.
            comment: Optional comment.

        Returns:
            True if approval was recorded.
        """
        request = self._requests.get(request_id)
        if not request:
            logger.error(f"Request {request_id} not found")
            return False

        if request.is_terminal or request.is_expired:
            logger.warning(f"Request {request_id} is already terminal or expired")
            return False

        # Record the approval
        approval_record = {
            "stage": stage.value,
            "approver": approver,
            "action": ApprovalAction.APPROVE.value,
            "comment": comment,
            "timestamp": time.time(),
        }
        request.approvals.append(approval_record)

        # Advance to next stage
        self._advance_stage(request, stage, approver, comment)

        request.updated_at = time.time()
        logger.info(f"Approval {request_id}: {approver} approved at {stage.value}")

        self._notify_status_change(request)
        return True

    def reject(
        self,
        request_id: str,
        approver: str,
        reason: str = "",
    ) -> bool:
        """Reject an approval request.

        Args:
            request_id: Request to reject.
            approver: Username of the approver.
            reason: Rejection reason.

        Returns:
            True if rejected.
        """
        request = self._requests.get(request_id)
        if not request or request.is_terminal:
            return False

        request.overall_status = ApprovalStatus.REJECTED
        request.current_stage = ApprovalStage.REJECTED
        request.updated_at = time.time()

        request.approvals.append({
            "stage": request.current_stage.value,
            "approver": approver,
            "action": ApprovalAction.REJECT.value,
            "comment": reason,
            "timestamp": time.time(),
        })

        logger.info(f"Request {request_id} rejected by {approver}: {reason}")
        self._notify_status_change(request)
        return True

    def final_approve(
        self,
        request_id: str,
        approvers: List[str],
        comments: Optional[List[str]] = None,
    ) -> bool:
        """Perform final approval (may require multiple approvers).

        Args:
            request_id: Request to final-approve.
            approvers: List of approver usernames.
            comments: Optional per-approver comments.

        Returns:
            True if final approval succeeded.
        """
        request = self._requests.get(request_id)
        if not request or request.is_terminal:
            return False

        # Check dual-approval requirement
        if self.config.require_dual_approval and len(approvers) < 2:
            logger.warning(
                f"Dual approval required for {request_id}, "
                f"got {len(approvers)} approver(s)"
            )
            return False

        # Check required approvers
        if request.required_approvers:
            missing = set(request.required_approvers) - set(approvers)
            if missing:
                logger.warning(
                    f"Missing required approvers for {request_id}: {missing}"
                )
                return False

        comments = comments or [""] * len(approvers)

        for approver, comment in zip(approvers, comments):
            request.approvals.append({
                "stage": ApprovalStage.FINAL_APPROVAL.value,
                "approver": approver,
                "action": ApprovalAction.APPROVE.value,
                "comment": comment,
                "timestamp": time.time(),
            })

        request.current_stage = ApprovalStage.APPROVED
        request.overall_status = ApprovalStatus.APPROVED
        request.updated_at = time.time()

        logger.info(
            f"Request {request_id} FINAL APPROVED by {approvers}"
        )

        # Move to history
        self._archive_request(request)

        self._notify_status_change(request)
        return True

    def request_changes(
        self, request_id: str, approver: str, comment: str
    ) -> bool:
        """Request changes on a submission (send back to submitter)."""
        request = self._requests.get(request_id)
        if not request or request.is_terminal:
            return False

        request.approvals.append({
            "stage": request.current_stage.value,
            "approver": approver,
            "action": ApprovalAction.REQUEST_CHANGES.value,
            "comment": comment,
            "timestamp": time.time(),
        })
        request.comments.append({
            "author": approver,
            "comment": comment,
            "timestamp": time.time(),
        })

        logger.info(f"Changes requested for {request_id} by {approver}: {comment}")
        self._notify_status_change(request)
        return True

    # ------------------------------------------------------------------
    # Internal Workflow
    # ------------------------------------------------------------------

    def _advance_stage(
        self,
        request: ApprovalRequest,
        completed_stage: ApprovalStage,
        approver: str,
        comment: str,
    ) -> None:
        """Advance to the next approval stage."""
        stages = self._get_required_stages()

        try:
            current_idx = stages.index(completed_stage)
            next_idx = current_idx + 1
        except ValueError:
            # Stage not in required stages, maybe a custom stage
            next_idx = len(stages)

        if next_idx < len(stages):
            request.current_stage = stages[next_idx]
            logger.info(
                f"Request {request.request_id} advanced to {stages[next_idx].value}"
            )
        else:
            # All stages complete — final approval needed
            if not self.config.require_final_approval:
                request.current_stage = ApprovalStage.APPROVED
                request.overall_status = ApprovalStatus.APPROVED
                self._archive_request(request)
                logger.info(f"Request {request.request_id} auto-approved (no final approval required)")

    def _archive_request(self, request: ApprovalRequest) -> None:
        """Move a completed request to history."""
        self._history.append(request)
        # Keep in active for a short period then remove
        # (For testing, we keep it)

    # ------------------------------------------------------------------
    # Check Expiration
    # ------------------------------------------------------------------

    def check_expired(self) -> List[ApprovalRequest]:
        """Check for and expire any timed-out requests.

        Returns:
            List of newly expired requests.
        """
        expired = []
        for request in list(self._requests.values()):
            if not request.is_terminal and request.is_expired:
                request.overall_status = ApprovalStatus.EXPIRED
                request.current_stage = ApprovalStage.REJECTED
                expired.append(request)
                logger.warning(
                    f"Request {request.request_id} expired: "
                    f"{request.model_name} v{request.model_version}"
                )
        return expired

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_request(self, request_id: str) -> Optional[ApprovalRequest]:
        """Get an approval request by ID."""
        return self._requests.get(request_id)

    def list_requests(
        self,
        status: Optional[ApprovalStatus] = None,
        stage: Optional[ApprovalStage] = None,
        model_name: Optional[str] = None,
    ) -> List[ApprovalRequest]:
        """List approval requests with filters."""
        requests = list(self._requests.values())
        if status:
            requests = [r for r in requests if r.overall_status == status]
        if stage:
            requests = [r for r in requests if r.current_stage == stage]
        if model_name:
            requests = [r for r in requests if r.model_name == model_name]
        return sorted(requests, key=lambda r: r.created_at, reverse=True)

    def get_pending_approvals(self, approver: str) -> List[ApprovalRequest]:
        """Get all requests pending approval from a specific approver."""
        pending = []
        for request in self._requests.values():
            if request.is_terminal:
                continue
            if approver in request.required_approvers:
                pending.append(request)
        return pending

    def get_pending_count(self) -> int:
        """Get count of pending approval requests."""
        return sum(
            1 for r in self._requests.values()
            if r.overall_status == ApprovalStatus.PENDING
        )

    def cancel_request(self, request_id: str, cancelled_by: str = "system") -> bool:
        """Cancel a pending approval request."""
        request = self._requests.get(request_id)
        if not request or request.is_terminal:
            return False

        request.current_stage = ApprovalStage.CANCELLED
        request.overall_status = ApprovalStatus.REJECTED  # treated as rejected
        request.updated_at = time.time()
        request.approvals.append({
            "stage": ApprovalStage.CANCELLED.value,
            "approver": cancelled_by,
            "action": ApprovalAction.REJECT.value,
            "comment": "Cancelled",
            "timestamp": time.time(),
        })
        return True

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    def on_status_change(self, callback: Callable) -> None:
        """Register a callback for status changes."""
        self._on_status_change.append(callback)

    def _notify_status_change(self, request: ApprovalRequest) -> None:
        for cb in self._on_status_change:
            try:
                cb(request)
            except Exception as e:
                logger.error(f"Status change callback error: {e}")

    def reset(self) -> None:
        """Reset state (for testing)."""
        self._requests.clear()
        self._history.clear()
