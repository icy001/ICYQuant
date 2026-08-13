"""
Approval Engine — manages approval workflows for decisions requiring review.
"""

from __future__ import annotations

import uuid
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, auto
from typing import Any, Dict, List, Optional

from .approval_request import ApprovalRequest, ApprovalRequestStatus
from .approval_result import ApprovalResult, ApprovalDecision
from .approval_workflow import ApprovalWorkflow, ApprovalWorkflowStep
from .approval_requirement import ApprovalRequirement, ApprovalLevel
from .decision_context import DecisionContext
from .decision_request import DecisionRequest

# Commit 28 Part 1.3 — four-eyes approval & separation of duties
from .approval import (
    Approval,
    ApprovalState,
    approve as _approve,
    consume as _consume,
    expire_approval as _expire_approval,
    reject as _reject,
    validate_binding,
)
from .approval_rule import ApprovalRule, is_eligible as _is_eligible
from .audit import ApprovalAuditEvent, ApprovalAuditEventType, ApprovalAuditStore
from .decision import DecisionEffect, GovernanceDecision


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


# ------------------------------------------------------------------
# Commit 28 Part 1.3 — Governance Approval Engine (Four-Eyes Control)
# ------------------------------------------------------------------


class GovernanceApprovalEngine:
    """Drives the governance approval state machine (Commit 28 Part 1.3).

    Maps an Approval (resource + action) to its ApprovalRule, verifies
    approver eligibility (four-eyes / separation of duties), advances
    the state machine and records immutable approval audit events.

    Pipeline: Request -> Approval Rule -> Eligible Approver -> Four-Eyes
    -> APPROVED -> Governance Re-Evaluation -> CONSUMED -> Control Plane.
    """

    def __init__(
        self,
        rules: tuple[ApprovalRule, ...] = (),
        auditor: Optional[ApprovalAuditStore] = None,
    ):
        self._rules: List[ApprovalRule] = list(rules)
        self._auditor = auditor if auditor is not None else ApprovalAuditStore()
        # Authoritative state ledger: Approvals are frozen dataclasses, so
        # the engine tracks the latest lifecycle state by approval_id.
        # This is what makes replay protection possible.
        self._states: Dict[str, ApprovalState] = {}

    @property
    def auditor(self) -> ApprovalAuditStore:
        return self._auditor

    def current_state(self, approval_id: str) -> Optional[ApprovalState]:
        """Latest tracked lifecycle state of an approval, if known."""
        return self._states.get(approval_id)

    def _track(self, approval: Approval) -> None:
        self._states[approval.approval_id] = approval.state

    def register_rule(self, rule: ApprovalRule) -> None:
        """Register an approval rule for a resource+action pair."""
        self._rules.append(rule)

    def find_rule(
        self,
        resource: str,
        action: str,
    ) -> Optional[ApprovalRule]:
        """Return the first rule governing the resource+action, if any."""
        for rule in self._rules:
            if rule.matches(resource, action):
                return rule
        return None

    def create_request(self, approval: Approval) -> Approval:
        """Request -> find the governing ApprovalRule.

        Raises ValueError when no rule governs this resource+action and
        records an APPROVAL_CREATED audit event on success.
        """
        rule = self.find_rule(approval.resource, approval.action)
        if rule is None:
            raise ValueError("approval rule not found")

        self._auditor.record(
            ApprovalAuditEvent(
                event_id=f"AE-{uuid.uuid4().hex[:12]}",
                event_type=ApprovalAuditEventType.APPROVAL_CREATED,
                timestamp=approval.requested_at
                or datetime.now(timezone.utc),
                approval_id=approval.approval_id,
                resource=approval.resource,
                action=approval.action,
                requester=approval.requested_by,
                incident_id=approval.incident_id,
                reason=f"rule={rule.rule_id}",
            )
        )
        self._track(approval)
        return approval

    def is_eligible(
        self,
        approver_id: str,
        approver_roles,
        approval: Approval,
    ) -> bool:
        """Four-eyes eligibility: different principal + required role."""
        rule = self.find_rule(approval.resource, approval.action)
        if rule is None:
            return False
        return _is_eligible(approver_id, approver_roles, approval, rule)

    def approve(
        self,
        approval: Approval,
        approver_id: str,
        now: datetime,
        approver_roles=(),
    ) -> Approval:
        """Approve a pending approval after eligibility checks.

        Self-approval and missing roles raise PermissionError; an
        expired or non-pending approval raises ValueError.
        """
        rule = self.find_rule(approval.resource, approval.action)
        if rule is None:
            raise ValueError("approval rule not found")
        if not _is_eligible(approver_id, approver_roles, approval, rule):
            if approval.requested_by == approver_id:
                raise PermissionError("requester cannot approve own request")
            raise PermissionError("approver lacks required role")

        result = _approve(approval, approver_id, now)
        self._auditor.record(
            ApprovalAuditEvent(
                event_id=f"AE-{uuid.uuid4().hex[:12]}",
                event_type=ApprovalAuditEventType.APPROVAL_APPROVED,
                timestamp=now,
                approval_id=approval.approval_id,
                resource=approval.resource,
                action=approval.action,
                requester=approval.requested_by,
                actor=approver_id,
                incident_id=approval.incident_id,
            )
        )
        self._track(result)
        return result

    def reject(
        self,
        approval: Approval,
        approver_id: str,
        reason: str,
        approver_roles=(),
    ) -> Approval:
        """Reject a pending approval with a mandatory reason."""
        rule = self.find_rule(approval.resource, approval.action)
        if rule is None:
            raise ValueError("approval rule not found")
        if not _is_eligible(approver_id, approver_roles, approval, rule):
            if approval.requested_by == approver_id:
                raise PermissionError("requester cannot reject own request")
            raise PermissionError("approver lacks required role")

        result = _reject(approval, approver_id, reason)
        self._auditor.record(
            ApprovalAuditEvent(
                event_id=f"AE-{uuid.uuid4().hex[:12]}",
                event_type=ApprovalAuditEventType.APPROVAL_REJECTED,
                timestamp=datetime.now(timezone.utc),
                approval_id=approval.approval_id,
                resource=approval.resource,
                action=approval.action,
                requester=approval.requested_by,
                actor=approver_id,
                incident_id=approval.incident_id,
                reason=reason,
            )
        )
        self._track(result)
        return result

    def expire(self, approval: Approval, now=None) -> Approval:
        """PENDING -> EXPIRED (auto-expire after the approval timeout)."""
        result = _expire_approval(approval, now)
        self._auditor.record(
            ApprovalAuditEvent(
                event_id=f"AE-{uuid.uuid4().hex[:12]}",
                event_type=ApprovalAuditEventType.APPROVAL_EXPIRED,
                timestamp=now or datetime.now(timezone.utc),
                approval_id=approval.approval_id,
                resource=approval.resource,
                action=approval.action,
                requester=approval.requested_by,
                incident_id=approval.incident_id,
            )
        )
        self._track(result)
        return result

    def consume(self, approval: Approval) -> Approval:
        """APPROVED -> CONSUMED (single-use / replay protection)."""
        result = _consume(approval)
        self._auditor.record(
            ApprovalAuditEvent(
                event_id=f"AE-{uuid.uuid4().hex[:12]}",
                event_type=ApprovalAuditEventType.APPROVAL_CONSUMED,
                timestamp=datetime.now(timezone.utc),
                approval_id=approval.approval_id,
                resource=approval.resource,
                action=approval.action,
                requester=approval.requested_by,
                incident_id=approval.incident_id,
            )
        )
        self._track(result)
        return result

    def authorize_execution(
        self,
        approval: Approval,
        decision: GovernanceDecision,
        now: datetime,
        resource: str | None = None,
        action: str | None = None,
        incident_id: str | None = None,
        requester: str | None = None,
        policy_id: str | None = None,
    ) -> GovernanceDecision:
        """Re-evaluation gate: APPROVED -> RE-EVALUATE -> ALLOW -> CONSUME.

        An approval never bypasses the current governance policy: the
        governance decision must be ALLOW at the moment of execution.
        A consumed / unapproved / expired approval blocks execution
        (replay protection), and a binding mismatch blocks using an
        approval for a different resource / action / incident / policy.
        Returns the decision the caller may act on.
        """
        if decision.effect != DecisionEffect.ALLOW:
            self._auditor.record(
                ApprovalAuditEvent(
                    event_id=f"AE-{uuid.uuid4().hex[:12]}",
                    event_type=ApprovalAuditEventType.APPROVAL_DENIED,
                    timestamp=now,
                    approval_id=approval.approval_id,
                    resource=approval.resource,
                    action=approval.action,
                    requester=approval.requested_by,
                    incident_id=approval.incident_id,
                    reason=f"governance re-evaluation denied: {decision.reason}",
                )
            )
            return decision

        try:
            validate_binding(
                approval,
                resource or approval.resource,
                action or approval.action,
                incident_id=incident_id,
                requester=requester,
                policy_id=policy_id,
            )
        except ValueError as exc:
            return self._denied(
                approval, decision, now, f"approval binding mismatch: {exc}"
            )

        state = self._states.get(approval.approval_id, approval.state)

        if state == ApprovalState.CONSUMED:
            return self._denied(
                approval, decision, now, "approval already consumed"
            )

        if state != ApprovalState.APPROVED:
            return self._denied(
                approval, decision, now, "approval not approved"
            )

        if approval.expires_at is not None and now >= approval.expires_at:
            return self._denied(approval, decision, now, "approval expired")

        self.consume(approval)
        return decision

    def _denied(
        self,
        approval: Approval,
        decision: GovernanceDecision,
        now: datetime,
        reason: str,
    ) -> GovernanceDecision:
        self._auditor.record(
            ApprovalAuditEvent(
                event_id=f"AE-{uuid.uuid4().hex[:12]}",
                event_type=ApprovalAuditEventType.APPROVAL_DENIED,
                timestamp=now,
                approval_id=approval.approval_id,
                resource=approval.resource,
                action=approval.action,
                requester=approval.requested_by,
                incident_id=approval.incident_id,
                reason=reason,
            )
        )
        return GovernanceDecision(
            effect=DecisionEffect.DENY,
            reason=reason,
            policy_id=decision.policy_id,
            approval_required=False,
        )
