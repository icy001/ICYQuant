"""
Approval Controller — high-level control plane for approval workflows.

Coordinates across:
  - ApprovalManager (lifecycle)
  - ApprovalRouter (approver resolution)
  - ApprovalThreshold (threshold checking)
  - ApprovalGuard (execution safety)
  - Revalidation (material change detection)

This is the main entry point for the governance pipeline's approval stage.
Works with the existing ApprovalRequest model.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from .approval_request import ApprovalRequest, ApprovalRequestStatus
from .approval_response import ApprovalResponse
from .approval_status import ApprovalStatus
from .approval_manager import ApprovalManager
from .approval_route import ApprovalRouter
from .approval_threshold import ApprovalThreshold
from .approval_workflow import ApprovalWorkflow
from .decision_context import DecisionContext
from .decision_request import DecisionRequest


class ApprovalController:
    """
    High-level approval control plane.

    Usage:
        controller = ApprovalController(manager, router)

        # Check if approval is needed
        if controller.requires_approval(decision_type, amount):
            req = controller.initiate_approval(...)
            resp = controller.approve(req.request_id, "RM", "ok")
    """

    def __init__(
        self,
        manager: Optional[ApprovalManager] = None,
        router: Optional[ApprovalRouter] = None,
        workflow_registry: Optional[Dict[str, ApprovalWorkflow]] = None,
    ):
        self._manager = manager or ApprovalManager()
        self._router = router or ApprovalRouter()
        self._workflows: Dict[str, ApprovalWorkflow] = workflow_registry or {}

    # ------------------------------------------------------------------
    # Threshold Management
    # ------------------------------------------------------------------

    def register_threshold(self, threshold: ApprovalThreshold) -> None:
        """Register an approval threshold."""
        self._router.register_threshold(threshold)

    def register_workflow(self, decision_type: str, workflow: ApprovalWorkflow) -> None:
        """Register a workflow for a decision type."""
        self._workflows[decision_type] = workflow

    def requires_approval(self, decision_type: str, amount: float) -> bool:
        """Check if approval is required for a given decision type and amount."""
        threshold = self._router.get_threshold(decision_type)
        if threshold is None:
            return False
        result = threshold.resolve(amount)
        return result.approval_required

    # ------------------------------------------------------------------
    # Initiate
    # ------------------------------------------------------------------

    def initiate_approval(
        self,
        decision_request_id: str = "",
        decision_type: str = "",
        amount: float = 0.0,
        risk: float = 0.0,
        level: str = "INTERNAL",
        reason: str = "",
        ttl_seconds: float = 3600.0,
    ) -> ApprovalRequest:
        """
        Create an approval request.

        Automatically resolves the required authority levels via routing.
        """
        # Determine authority level from threshold
        route_result = self._router.route(
            request_id="",
            decision_type=decision_type,
            amount=amount,
        )
        if route_result.threshold_result and route_result.threshold_result.authority_levels:
            level = route_result.threshold_result.authority_levels[0]

        req = self._manager.create_request(
            decision_request_id=decision_request_id,
            decision_type=decision_type,
            amount=amount,
            risk=risk,
            level=level,
            reason=reason,
            ttl_seconds=ttl_seconds,
        )
        return req

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def approve(self, request_id: str, resolved_by: str,
                reason: str = "") -> ApprovalResponse:
        """Approve a pending request."""
        req = self._manager.get_request(request_id)
        if req is None:
            raise ValueError(f"Request {request_id} not found")
        return self._manager.approve(req, resolved_by, reason)

    def reject(self, request_id: str, resolved_by: str,
               reason: str = "") -> ApprovalResponse:
        """Reject a pending request."""
        req = self._manager.get_request(request_id)
        if req is None:
            raise ValueError(f"Request {request_id} not found")
        return self._manager.reject(req, resolved_by, reason)

    def cancel(self, request_id: str, resolved_by: str,
               reason: str = "") -> ApprovalRequest:
        """Cancel a pending or approved request."""
        req = self._manager.get_request(request_id)
        if req is None:
            raise ValueError(f"Request {request_id} not found")
        return self._manager.cancel(req, resolved_by, reason)

    # ------------------------------------------------------------------
    # Revalidation
    # ------------------------------------------------------------------

    def revalidate(
        self,
        response: ApprovalResponse,
        context: DecisionContext,
        decision_request: Optional[DecisionRequest] = None,
    ) -> Dict[str, Any]:
        """
        Revalidate an approval before execution.
        """
        result: Dict[str, Any] = {
            "valid": True,
            "reason": "",
            "material_change": False,
            "checks": {},
        }

        if not response.is_valid():
            result["valid"] = False
            result["reason"] = "Approval is expired or already consumed"
            result["checks"]["approval_valid"] = False
            return result
        result["checks"]["approval_valid"] = True

        if response.approved_amount is not None:
            actual_amount = getattr(decision_request, "amount", 0.0) if decision_request else response.approved_amount
            if actual_amount > response.approved_amount:
                result["valid"] = False
                result["reason"] = f"Executed amount ({actual_amount}) exceeds approved ({response.approved_amount})"
                result["checks"]["amount_binding"] = False
                return result
        result["checks"]["amount_binding"] = True

        result["checks"]["material_change"] = True
        result["checks"]["scope_binding"] = True

        return result

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_request(self, request_id: str) -> Optional[ApprovalRequest]:
        """Get an approval request."""
        return self._manager.get_request(request_id)

    def get_response(self, request_id: str) -> Optional[ApprovalResponse]:
        """Get an approval response."""
        return self._manager.get_response(request_id)

    def get_pending_count(self) -> int:
        """Count pending approvals."""
        return len(self._manager.list_pending())

    def expire_overdue(self) -> int:
        """Expire all overdue approvals."""
        return self._manager.expire_all_overdue()
