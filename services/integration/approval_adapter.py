"""
Approval Adapter — bridges Approval Engine into the integration control flow.

Commit 21 Part 1.1: translates approval results into a normalized
approval_context consumed by ApprovalGate.
"""

from __future__ import annotations

import time
from typing import Any, Dict, Optional


class ApprovalAdapter:
    """Bridges Approval Engine to integration layer.

    Domain (Approval) → Adapter → Integration Layer (ApprovalGate)
    """

    @staticmethod
    def build_approval_context(
        approval_id: str = "",
        status: str = "PENDING",
        approved_amount: float = 0.0,
        approved_action: str = "",
        consumed: bool = False,
        valid_until: float = 0.0,
        policy_version: str = "",
        decision_id: str = "",
        approved: bool = False,
        **kwargs,
    ) -> Dict[str, Any]:
        """Build an approval context dict for integration gates."""
        return {
            "approval_id": approval_id,
            "status": status,
            "approved_amount": approved_amount,
            "approved_action": approved_action,
            "consumed": consumed,
            "valid_until": valid_until,
            "policy_version": policy_version,
            "decision_id": decision_id,
            "approved": approved,
            **kwargs,
        }

    @staticmethod
    def from_approval_result(result: Dict[str, Any]) -> Dict[str, Any]:
        """Convert approval engine result to integration context."""
        return {
            "approval_id": result.get("approval_id", ""),
            "status": "APPROVED" if result.get("approved") else result.get("status", "REJECTED"),
            "approved_amount": result.get("approved_amount", result.get("amount", 0.0)),
            "approved_action": result.get("approved_action", result.get("action", "")),
            "consumed": result.get("consumed", False),
            "valid_until": result.get("valid_until", result.get("expires_at", 0.0)),
            "policy_version": result.get("policy_version", ""),
            "decision_id": result.get("decision_id", ""),
            "approved": result.get("approved", False),
            "reason": result.get("reason", ""),
            "level": result.get("level", ""),
            "approval_required": result.get("approval_required", False),
        }

    @staticmethod
    def from_approval_response(response: Any) -> Dict[str, Any]:
        """Convert ApprovalResponse to integration context."""
        return {
            "approval_id": getattr(response, "approval_id", ""),
            "status": getattr(getattr(response, "status", None), "name", "PENDING"),
            "approved_amount": getattr(response, "approved_amount", 0.0),
            "approved_action": getattr(response, "approved_action", ""),
            "consumed": getattr(response, "consumed", False),
            "valid_until": getattr(response, "valid_until", 0.0),
            "policy_version": getattr(response, "policy_version", ""),
            "decision_id": getattr(response, "decision_id", ""),
            "approved": getattr(response, "approved", False),
            "reason": getattr(response, "reason", ""),
            "is_valid": getattr(response, "is_valid", lambda: False)(),
        }

    @staticmethod
    def check_valid(
        response: Any, requested_amount: float = 0.0, current_time: Optional[float] = None
    ) -> Dict[str, Any]:
        """Check if an approval response is valid for the given parameters."""
        now = current_time or time.time()
        status = getattr(getattr(response, "status", None), "name", "UNKNOWN")
        return {
            "is_approved": status == "APPROVED",
            "is_consumed": getattr(response, "consumed", False),
            "is_expired": getattr(response, "valid_until", 0) > 0
                          and now > getattr(response, "valid_until", 0),
            "amount_sufficient": not getattr(response, "approved_amount", 0) or
                                 requested_amount <= getattr(response, "approved_amount", float("inf")),
            "is_valid": getattr(response, "is_valid", lambda: False)(),
        }
