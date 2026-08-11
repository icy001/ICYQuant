"""Approval Gateway — Human-in-the-Loop (HITL) approval gateway for autonomous trading.

Pipeline:
    Portfolio + Risk + Compliance -> ApprovalGateway.request_approval()
        -> Check if approval is required (based on mode and confidence)
        -> If YES -> Queue for human review
        -> If NO -> Auto-approve and continue
        -> Output ApprovalDecision

Configurable modes:
    - none: Fully autonomous (no human approval)
    - significant_only: Only require approval for high-impact decisions
    - always: Always require human approval (default)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    AUTO_APPROVED = "auto_approved"
    EXPIRED = "expired"


class ApprovalMode(str, Enum):
    NONE = "none"
    SIGNIFICANT_ONLY = "significant_only"
    ALWAYS = "always"


@dataclass
class ApprovalDecision:
    """An approval decision from the gateway.

    Attributes:
        decision_id: Unique identifier.
        workflow_id: Related workflow.
        status: Approval status.
        approved_by: Who approved (human name or "auto").
        reason: Reason for the decision.
        conditions: Any conditions attached to the approval.
        requested_at: When approval was requested.
        decided_at: When the decision was made.
    """

    decision_id: str = ""
    workflow_id: str = ""
    status: ApprovalStatus = ApprovalStatus.PENDING
    approved_by: str = ""
    reason: str = ""
    conditions: List[str] = field(default_factory=list)
    requested_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    decided_at: Optional[datetime] = None

    @property
    def is_approved(self) -> bool:
        return self.status in (ApprovalStatus.APPROVED, ApprovalStatus.AUTO_APPROVED)


class ApprovalGateway:
    """Human-in-the-Loop approval gateway.

    Controls whether autonomous workflows require human approval based
    on configurable policies. Defaults to always requiring approval
    for live trading, with configurable bypass for research/paper modes.

    Supports:
        - Configurable approval modes (none / significant_only / always)
        - Confidence-based auto-approval
        - Human review queue
        - Approval conditions
        - Timeout-based expiry

    Usage:
        config = AutonomyConfig(mode=AutonomyMode.LIVE_TRADING)
        gateway = ApprovalGateway(config=config)
        await gateway.initialize()
        decision = await gateway.request_approval(workflow_context)
        if decision.is_approved:
            proceed()
    """

    def __init__(
        self,
        config: Optional[Any] = None,
        default_mode: ApprovalMode = ApprovalMode.ALWAYS,
        confidence_threshold: float = 0.80,
        request_timeout_sec: float = 3600.0,
    ) -> None:
        self._mode = ApprovalMode.ALWAYS
        self._confidence_threshold = confidence_threshold
        self._request_timeout_sec = request_timeout_sec
        self._decisions: List[ApprovalDecision] = []
        self._pending: Dict[str, ApprovalDecision] = {}
        self._counter: int = 0
        self._initialized: bool = False

        if config:
            self._mode = self._map_approval_mode(config.approval_mode)
            self._confidence_threshold = config.confidence_threshold

        logger.info(
            "ApprovalGateway created (mode=%s, confidence_threshold=%.2f)",
            self._mode.value, confidence_threshold,
        )

    @staticmethod
    def _map_approval_mode(mode_value: Any) -> ApprovalMode:
        if mode_value is None:
            return ApprovalMode.ALWAYS
        val = mode_value.value if hasattr(mode_value, "value") else str(mode_value)
        try:
            return ApprovalMode(val)
        except ValueError:
            return ApprovalMode.ALWAYS

    async def initialize(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        logger.info("ApprovalGateway initialized")

    async def shutdown(self) -> None:
        self._decisions.clear()
        self._pending.clear()
        self._initialized = False
        logger.info("ApprovalGateway shutdown complete")

    async def request_approval(
        self,
        workflow_context: Any,
        confidence: Optional[float] = None,
    ) -> bool:
        """Request approval for a workflow.

        Args:
            workflow_context: The workflow context.
            confidence: Optional confidence score for auto-approval.

        Returns:
            True if approved, False otherwise.
        """
        wf_id = getattr(workflow_context, "workflow_id", "unknown")
        self._counter += 1
        decision = ApprovalDecision(
            decision_id=f"appr_{self._counter}",
            workflow_id=wf_id,
        )

        # Mode: none -> auto-approve everything
        if self._mode == ApprovalMode.NONE:
            decision.status = ApprovalStatus.AUTO_APPROVED
            decision.approved_by = "auto"
            decision.reason = "Autonomous mode — no approval required"
            decision.decided_at = datetime.now(timezone.utc)
            self._decisions.append(decision)
            logger.info("Approval auto-approved (mode=none): %s", wf_id)
            return True

        # Mode: significant_only -> auto-approve if confidence is high
        if self._mode == ApprovalMode.SIGNIFICANT_ONLY and confidence is not None:
            if confidence >= self._confidence_threshold:
                decision.status = ApprovalStatus.AUTO_APPROVED
                decision.approved_by = "auto"
                decision.reason = f"Confidence {confidence:.2f} >= threshold {self._confidence_threshold:.2f}"
                decision.decided_at = datetime.now(timezone.utc)
                self._decisions.append(decision)
                logger.info("Approval auto-approved (confidence=%.2f): %s", confidence, wf_id)
                return True

        # Mode: always OR significant_only with low confidence -> human review
        decision.status = ApprovalStatus.PENDING
        self._pending[wf_id] = decision
        self._decisions.append(decision)
        logger.info("Approval pending (human review required): %s", wf_id)
        return False

    async def human_approve(self, workflow_id: str, approved_by: str = "human", reason: str = "") -> bool:
        decision = self._pending.get(workflow_id)
        if decision is None:
            logger.warning("No pending approval for: %s", workflow_id)
            return False
        decision.status = ApprovalStatus.APPROVED
        decision.approved_by = approved_by
        decision.reason = reason or "Human approved"
        decision.decided_at = datetime.now(timezone.utc)
        self._pending.pop(workflow_id, None)
        logger.info("Human approved: %s (by=%s)", workflow_id, approved_by)
        return True

    async def human_reject(self, workflow_id: str, reason: str = "") -> None:
        decision = self._pending.get(workflow_id)
        if decision is None:
            logger.warning("No pending approval for: %s", workflow_id)
            return
        decision.status = ApprovalStatus.REJECTED
        decision.reason = reason or "Human rejected"
        decision.decided_at = datetime.now(timezone.utc)
        self._pending.pop(workflow_id, None)
        logger.info("Human rejected: %s (reason=%s)", workflow_id, reason)

    def get_pending_approvals(self) -> List[Dict[str, Any]]:
        return [
            {
                "decision_id": d.decision_id,
                "workflow_id": d.workflow_id,
                "requested_at": d.requested_at.isoformat(),
            }
            for d in self._pending.values()
        ]

    def get_summary(self) -> Dict[str, Any]:
        total = len(self._decisions)
        auto = sum(1 for d in self._decisions if d.status == ApprovalStatus.AUTO_APPROVED)
        human = sum(1 for d in self._decisions if d.status == ApprovalStatus.APPROVED)
        rejected = sum(1 for d in self._decisions if d.status == ApprovalStatus.REJECTED)
        pending = len(self._pending)
        return {
            "initialized": self._initialized,
            "mode": self._mode.value,
            "total": total,
            "auto_approved": auto,
            "human_approved": human,
            "rejected": rejected,
            "pending": pending,
        }
