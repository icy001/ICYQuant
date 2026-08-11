"""
Approval Engine — manages approval workflows for decisions requiring review.
"""

from __future__ import annotations

import uuid
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional

from .approval_request import ApprovalRequest, ApprovalRequestStatus
from .approval_result import ApprovalResult, ApprovalDecision
from .approval_workflow import ApprovalWorkflow, ApprovalWorkflowStep
from .approval_requirement import ApprovalRequirement, ApprovalLevel
from .decision_context import DecisionContext
from .decision_request import DecisionRequest


class ApprovalEngine:
    """
    Manages the full approval lifecycle:
      - Checks if approval is required
      - Routes through approval workflows
      - Resolves approval decisions
    """

    def __init__(
        self,
        workflows: Optional[List[ApprovalWorkflow]] = None,
        requirements: Optional[List[ApprovalRequirement]] = None,
    ):
        self._workflows: Dict[str, ApprovalWorkflow] = {}
        self._requirements: List[ApprovalRequirement] = requirements or []
        self._pending: Dict[str, ApprovalRequest] = {}
        self._history: List[ApprovalResult] = []

        for wf in (workflows or []):
            self._workflows[wf.workflow_id] = wf

        if not self._requirements:
            self._setup_default_requirements()

    # ------------------------------------------------------------------
    # Workflow management
    # ------------------------------------------------------------------

    def register_workflow(self, workflow: ApprovalWorkflow) -> None:
        self._workflows[workflow.workflow_id] = workflow

    def register_requirement(self, requirement: ApprovalRequirement) -> None:
        self._requirements.append(requirement)

    # ------------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------------

    def evaluate(
        self, request: DecisionRequest, context: DecisionContext, governance_evaluation: Any = None
    ) -> Dict[str, Any]:
        """Evaluate whether approval is required and process it."""
        # Step 1: Check if approval is needed
        requirement = self._match_requirement(request)

        if requirement is None:
            return {
                "approved": True,
                "approval_required": False,
                "level": "NONE",
                "reason": "No approval required",
            }

        # Step 2: Create approval request
        approval_request = ApprovalRequest(
            request_id=f"APR-{uuid.uuid4().hex[:12]}",
            decision_request_id=request.request_id,
            decision_type=request.decision_type.name,
            amount=request.requested_amount,
            risk=request.additional_risk,
            level=requirement.approval_level,
            context=context.to_dict(),
        )
        self._pending[approval_request.request_id] = approval_request

        # Step 3: Route through workflow
        approval_workflow = self._get_workflow(requirement.approval_level)

        if approval_workflow:
            result = approval_workflow.process(approval_request, context)
        else:
            # Default: auto-approve internal
            result = ApprovalResult.approved(
                approval_request.request_id,
                decision_request_id=request.request_id,
                reason="Auto-approved (no workflow configured)",
            )

        approval_request.status = (
            ApprovalRequestStatus.APPROVED if result.decision == ApprovalDecision.APPROVED
            else ApprovalRequestStatus.REJECTED
        )
        self._history.append(result)

        return {
            "approved": result.decision == ApprovalDecision.APPROVED,
            "approval_required": True,
            "level": requirement.approval_level.name,
            "approval_id": result.approval_id,
            "reason": result.reason,
            "workflow_id": approval_workflow.workflow_id if approval_workflow else None,
        }

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_pending(self) -> List[ApprovalRequest]:
        return [r for r in self._pending.values()
                if r.status == ApprovalRequestStatus.PENDING]

    def get_history(self, limit: int = 100) -> List[ApprovalResult]:
        return self._history[-limit:]

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _match_requirement(self, request: DecisionRequest) -> Optional[ApprovalRequirement]:
        """Find the first matching approval requirement."""
        for req in self._requirements:
            if req.requires_approval(
                request_id=request.request_id,
                decision_type=request.decision_type.name,
                amount=request.requested_amount,
                risk=request.additional_risk,
                leverage=request.requested_leverage,
            ):
                return req
        return None

    def _get_workflow(self, level: ApprovalLevel) -> Optional[ApprovalWorkflow]:
        """Get the appropriate workflow for an approval level."""
        for wf in self._workflows.values():
            if wf.level == level:
                return wf

        # Default: internal auto-approve
        return ApprovalWorkflow.default_internal()

    def _setup_default_requirements(self) -> None:
        """Setup default approval requirements."""
        self._requirements = [
            ApprovalRequirement(
                name="Large Allocation",
                description="Allocations above 20M require institutional approval",
                decision_types=["CAPITAL_ALLOCATION"],
                min_amount=20_000_000,
                approval_level=ApprovalLevel.INSTITUTIONAL,
            ),
            ApprovalRequirement(
                name="Medium Allocation",
                description="Allocations between 5M and 20M require risk review",
                decision_types=["CAPITAL_ALLOCATION"],
                min_amount=5_000_000,
                max_amount=20_000_000,
                approval_level=ApprovalLevel.RISK_REVIEW,
            ),
            ApprovalRequirement(
                name="Leverage Change",
                description="Leverage changes require risk review",
                decision_types=["LEVERAGE_CHANGE"],
                min_leverage=1.0,
                approval_level=ApprovalLevel.RISK_REVIEW,
            ),
            ApprovalRequirement(
                name="Risk Budget Change",
                description="Risk budget changes require institutional approval",
                decision_types=["RISK_BUDGET_CHANGE"],
                min_risk=0.0,
                approval_level=ApprovalLevel.INSTITUTIONAL,
            ),
            ApprovalRequirement(
                name="Emergency Action",
                description="Emergency actions auto-approved for risk reduction",
                decision_types=["EMERGENCY_ACTION"],
                approval_level=ApprovalLevel.INTERNAL,
            ),
        ]
