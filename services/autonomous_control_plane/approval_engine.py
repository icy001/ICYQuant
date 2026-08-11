"""
Approval Engine — Human approval gate for autonomous decisions.

All decisions requiring human review pass through the Approval Engine,
which manages approval requests, gates, and human override actions.
"""

from __future__ import annotations

import uuid
import time
import logging
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ApprovalStatus(Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    OVERRIDDEN = "overridden"


class ApprovalEngine:
    """
    Manages human approval for autonomous decisions.

    Certain actions (e.g., L5+ autonomy operations, large capital
    allocations) require human approval before execution.
    """

    def __init__(self):
        self._requests: dict[str, dict] = {}
        self._overrides: list[dict] = []
        self._approval_count = 0
        self._rejection_count = 0

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def evaluate(self, context) -> object:
        """
        Evaluate whether a decision requires approval and if so,
        whether approval has been granted.
        """
        from .decision_result import DecisionResult

        scope = getattr(context, "requested_scope", "")
        action = getattr(context, "action", "")

        # Only certain scopes require approval
        requires_approval = (
            scope in ("production", "capital", "execution") or
            action in ("autonomous_execution", "full_autonomy", "allocate_capital")
        )

        if not requires_approval:
            return DecisionResult.allowed_result()

        approval_id = getattr(context, "approval_id", None)
        if approval_id:
            status = self.get_status(approval_id)
            if status == ApprovalStatus.APPROVED:
                return DecisionResult.allowed_result()
            elif status == ApprovalStatus.REJECTED:
                return DecisionResult.denied("Approval rejected")

        # Approval required but not granted
        return DecisionResult(
            allowed=False,
            reason="Awaiting human approval",
        )

    # ------------------------------------------------------------------
    # Request Management
    # ------------------------------------------------------------------

    def create_request(
        self,
        decision_id: str,
        requested_by: str,
        action: str,
        scope: str,
        details: Optional[dict] = None,
    ) -> str:
        """Create an approval request."""
        approval_id = str(uuid.uuid4())
        self._requests[approval_id] = {
            "approval_id": approval_id,
            "decision_id": decision_id,
            "requested_by": requested_by,
            "action": action,
            "scope": scope,
            "status": ApprovalStatus.PENDING,
            "created_at": time.time(),
            "details": details or {},
        }
        logger.info("Approval request %s created for %s", approval_id, decision_id)
        return approval_id

    def approve(self, approval_id: str, operator: str, comment: str = "") -> bool:
        """Approve a pending request."""
        req = self._requests.get(approval_id)
        if not req or req["status"] != ApprovalStatus.PENDING:
            return False
        req["status"] = ApprovalStatus.APPROVED
        req["approved_by"] = operator
        req["approved_at"] = time.time()
        req["comment"] = comment
        self._approval_count += 1
        return True

    def reject(self, approval_id: str, operator: str, reason: str = "") -> bool:
        """Reject a pending request."""
        req = self._requests.get(approval_id)
        if not req or req["status"] != ApprovalStatus.PENDING:
            return False
        req["status"] = ApprovalStatus.REJECTED
        req["rejected_by"] = operator
        req["rejected_at"] = time.time()
        req["rejection_reason"] = reason
        self._rejection_count += 1
        return True

    def get_status(self, approval_id: str) -> Optional[ApprovalStatus]:
        req = self._requests.get(approval_id)
        return req["status"] if req else None

    # ------------------------------------------------------------------
    # Human Override
    # ------------------------------------------------------------------

    async def override(
        self, decision_id: str, action: str, operator: str, reason: str
    ) -> bool:
        """
        Apply a human override to a pending or active decision.

        Actions: APPROVE, REJECT, PAUSE, RESUME, REDUCE_RISK,
                 FORCE_QUARANTINE, ROLLBACK, HALT
        """
        valid_actions = {
            "APPROVE", "REJECT", "PAUSE", "RESUME",
            "REDUCE_RISK", "FORCE_QUARANTINE", "ROLLBACK", "HALT",
        }
        if action not in valid_actions:
            return False

        self._overrides.append({
            "decision_id": decision_id,
            "action": action,
            "operator": operator,
            "reason": reason,
            "timestamp": time.time(),
        })

        logger.warning("Human override: %s → %s (%s) by %s", decision_id, action, reason, operator)
        return True

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    def stats(self) -> dict:
        return {
            "requests_total": len(self._requests),
            "approved": self._approval_count,
            "rejected": self._rejection_count,
            "pending": len([r for r in self._requests.values() if r["status"] == ApprovalStatus.PENDING]),
            "overrides_total": len(self._overrides),
        }
