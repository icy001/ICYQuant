"""
Approval Workflow — multi-step approval process.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional

from .approval_request import ApprovalRequest, ApprovalRequestStatus
from .approval_result import ApprovalResult, ApprovalDecision
from .approval_requirement import ApprovalLevel
from .decision_context import DecisionContext


@dataclass
class ApprovalWorkflowStep:
    """A single step in an approval workflow."""

    step_id: str = field(default_factory=lambda: f"STEP-{uuid.uuid4().hex[:8]}")
    name: str = ""
    description: str = ""

    # Evaluation
    condition: Optional[Callable[[ApprovalRequest, DecisionContext], bool]] = None

    # Action
    action: Optional[Callable[[ApprovalRequest, DecisionContext], ApprovalDecision]] = None

    # Default behavior
    default_decision: ApprovalDecision = ApprovalDecision.APPROVED

    def execute(self, request: ApprovalRequest, context: DecisionContext) -> ApprovalDecision:
        """Execute this workflow step."""
        if self.condition and not self.condition(request, context):
            return ApprovalDecision.APPROVED  # Skip

        if self.action:
            return self.action(request, context)

        return self.default_decision


class ApprovalWorkflow:
    """
    A multi-step approval workflow.
    Each step can conditionally run and return a decision.
    """

    def __init__(
        self,
        workflow_id: str = "",
        name: str = "",
        level: ApprovalLevel = ApprovalLevel.INTERNAL,
        steps: Optional[List[ApprovalWorkflowStep]] = None,
    ):
        self.workflow_id = workflow_id or f"WF-{uuid.uuid4().hex[:8]}"
        self.name = name
        self.level = level
        self.steps: List[ApprovalWorkflowStep] = steps or []

    def add_step(self, step: ApprovalWorkflowStep) -> None:
        self.steps.append(step)

    def process(
        self, request: ApprovalRequest, context: DecisionContext
    ) -> ApprovalResult:
        """Run through all workflow steps."""
        completed_steps = []

        for step in self.steps:
            decision = step.execute(request, context)
            completed_steps.append(step.step_id)

            if decision == ApprovalDecision.REJECTED:
                return ApprovalResult.rejected(
                    approval_request_id=request.request_id,
                    decision_request_id=request.decision_request_id,
                    reason=f"Rejected at step: {step.name}",
                    steps_completed=completed_steps,
                )

        # All steps passed
        return ApprovalResult.approved(
            approval_request_id=request.request_id,
            decision_request_id=request.decision_request_id,
            reason=f"Approved through workflow: {self.name}",
            steps_completed=completed_steps,
        )

    @classmethod
    def default_internal(cls) -> "ApprovalWorkflow":
        """Default internal auto-approve workflow."""
        return cls(
            workflow_id="WF-DEFAULT-INTERNAL",
            name="Default Internal Approval",
            level=ApprovalLevel.INTERNAL,
            steps=[
                ApprovalWorkflowStep(
                    name="Auto-approve",
                    description="Auto-approve for internal level decisions",
                    default_decision=ApprovalDecision.APPROVED,
                ),
            ],
        )

    @classmethod
    def risk_review_workflow(cls) -> "ApprovalWorkflow":
        """Risk review approval workflow."""
        def check_risk(request: ApprovalRequest, context: DecisionContext) -> ApprovalDecision:
            if context.survival_score < 70:
                return ApprovalDecision.REJECTED
            if context.risk_budget_available and request.amount:
                if request.amount > context.risk_budget_available:
                    return ApprovalDecision.REJECTED
            return ApprovalDecision.APPROVED

        return cls(
            workflow_id="WF-RISK-REVIEW",
            name="Risk Review Approval",
            level=ApprovalLevel.RISK_REVIEW,
            steps=[
                ApprovalWorkflowStep(
                    name="Survival Check",
                    description="Check capital survival score",
                    action=lambda req, ctx: (
                        ApprovalDecision.REJECTED if ctx.survival_score < 70
                        else ApprovalDecision.APPROVED
                    ),
                ),
                ApprovalWorkflowStep(
                    name="Risk Budget Check",
                    description="Check risk budget capacity",
                    action=check_risk,
                ),
            ],
        )

    @classmethod
    def institutional_workflow(cls) -> "ApprovalWorkflow":
        """Institutional approval workflow with multiple checks."""
        return cls(
            workflow_id="WF-INSTITUTIONAL",
            name="Institutional Approval",
            level=ApprovalLevel.INSTITUTIONAL,
            steps=[
                ApprovalWorkflowStep(
                    name="Risk Assessment",
                    description="Full risk impact assessment",
                    action=lambda req, ctx: (
                        ApprovalDecision.REJECTED if ctx.stress_survival_score < 70
                        else ApprovalDecision.APPROVED
                    ),
                ),
                ApprovalWorkflowStep(
                    name="Capacity Check",
                    description="Verify capacity constraints",
                    action=lambda req, ctx: (
                        ApprovalDecision.REJECTED
                        if (req.amount and ctx.strategy_capacity and req.amount > ctx.strategy_capacity)
                        else ApprovalDecision.APPROVED
                    ),
                ),
                ApprovalWorkflowStep(
                    name="Concentration Check",
                    description="Verify concentration limits",
                    action=lambda req, ctx: (
                        ApprovalDecision.REJECTED if ctx.current_concentration > 0.35
                        else ApprovalDecision.APPROVED
                    ),
                ),
            ],
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "name": self.name,
            "level": self.level.name,
            "steps_count": len(self.steps),
        }
