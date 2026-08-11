"""
Approval Route — routes approval requests to the correct approvers.

Determines WHO should approve a given request based on:
  - Decision type and amount
  - Authority grants
  - Delegations
  - Approval policy thresholds
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .authority_engine import AuthorityEngine
from .approval_policy import ApprovalPolicy, ApprovalLevel
from .approval_threshold import ApprovalThreshold, ThresholdResult
from .approval_step import ApprovalStep, StepType


@dataclass
class ApproverTarget:
    """An identified approver for a specific requirement."""

    approver_id: str
    approver_name: str = ""
    role: str = ""
    authority_level: str = ""
    authority_id: str = ""
    delegation_id: str = ""
    max_approval_amount: float = 0.0
    is_delegation: bool = False
    reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "approver_id": self.approver_id,
            "approver_name": self.approver_name,
            "role": self.role,
            "authority_level": self.authority_level,
            "authority_id": self.authority_id,
            "delegation_id": self.delegation_id,
            "max_approval_amount": self.max_approval_amount,
            "is_delegation": self.is_delegation,
            "reason": self.reason,
        }


@dataclass
class RouteResult:
    """The result of routing an approval request."""

    request_id: str
    decision_type: str
    amount: float

    # Resolved threshold
    threshold_result: Optional[ThresholdResult] = None

    # Identified approvers
    targets: List[ApproverTarget] = field(default_factory=list)

    # Whether approval is needed at all
    approval_required: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "decision_type": self.decision_type,
            "amount": self.amount,
            "threshold_result": self.threshold_result.to_dict() if self.threshold_result else None,
            "targets": [t.to_dict() for t in self.targets],
            "approval_required": self.approval_required,
        }


class ApprovalRouter:
    """
    Routes approval requests to the correct approvers.

    Uses ApprovalThreshold to determine which authority level is needed,
    then maps those levels to specific approvers via AuthorityEngine grants.
    """

    def __init__(self, authority_engine: Optional[AuthorityEngine] = None):
        self._authority_engine = authority_engine or AuthorityEngine()
        self._thresholds: Dict[str, ApprovalThreshold] = {}
        self._approval_policies: Dict[str, ApprovalPolicy] = {}

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register_threshold(self, threshold: ApprovalThreshold) -> None:
        """Register an approval threshold for a decision type."""
        self._thresholds[threshold.decision_type] = threshold

    def register_approval_policy(self, policy: ApprovalPolicy) -> None:
        """Register an approval policy."""
        self._approval_policies[policy.approval_policy_id] = policy

    # ------------------------------------------------------------------
    # Routing
    # ------------------------------------------------------------------

    def route(
        self,
        request_id: str,
        decision_type: str,
        amount: float,
    ) -> RouteResult:
        """
        Resolve which approvers are needed for a given request.

        Returns a RouteResult with the identified approvers.
        """
        result = RouteResult(
            request_id=request_id,
            decision_type=decision_type,
            amount=amount,
        )

        # 1. Resolve threshold
        threshold = self._thresholds.get(decision_type)
        if not threshold:
            result.approval_required = False
            return result

        threshold_result = threshold.resolve(amount)
        result.threshold_result = threshold_result
        result.approval_required = threshold_result.approval_required

        if not threshold_result.approval_required:
            return result

        # 2. Map authority levels to approvers
        for level in threshold_result.authority_levels:
            target = self._resolve_approver(level)
            if target:
                result.targets.append(target)

        return result

    def build_approval_steps(self, route_result: RouteResult) -> List[ApprovalStep]:
        """Build ApprovalStep objects from route targets."""
        steps: List[ApprovalStep] = []
        for idx, target in enumerate(route_result.targets):
            step = ApprovalStep(
                step_id=f"STEP-{route_result.request_id}-{idx + 1:03d}",
                name=f"{target.role} Approval",
                step_type=StepType.APPROVE,
                required_role=target.role,
                required_authority_level=target.authority_level,
                required=True,
                sequence_order=idx + 1,
            )
            step.assigned_approver = target.approver_id
            step.assigned_delegation_id = target.delegation_id
            steps.append(step)
        return steps

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _resolve_approver(self, authority_level: str) -> Optional[ApproverTarget]:
        """Map an authority level to a specific approver."""
        return ApproverTarget(
            approver_id=f"APPROVER-{authority_level}",
            approver_name=f"Approver for {authority_level}",
            role=authority_level,
            authority_level=authority_level,
            reason=f"Route resolved for level: {authority_level}",
        )

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_threshold(self, decision_type: str) -> Optional[ApprovalThreshold]:
        """Get registered threshold for a decision type."""
        return self._thresholds.get(decision_type)

    def list_thresholds(self) -> List[ApprovalThreshold]:
        """List all registered thresholds."""
        return list(self._thresholds.values())

    def list_approval_policies(self) -> List[ApprovalPolicy]:
        """List all registered approval policies."""
        return list(self._approval_policies.values())
