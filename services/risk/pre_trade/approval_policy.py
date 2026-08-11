"""
Approval Policy — Policy engine for automated and manual approval routing.

Determines whether a risk decision requires manual intervention based
on risk scores, rule triggers, and configurable thresholds.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class ApprovalMode(str, Enum):
    """Approval routing mode."""
    AUTO = "auto"            # Automatically approve/reject
    MANUAL = "manual"        # Always require manual approval
    HYBRID = "hybrid"        # Auto below threshold, manual above
    FOUR_EYES = "four_eyes"  # Two-person approval for high risk


class ApprovalAction(str, Enum):
    """Action taken by the approval engine."""
    AUTO_APPROVE = "auto_approve"
    AUTO_REJECT = "auto_reject"
    ROUTE_TO_APPROVER = "route_to_approver"
    ROUTE_TO_ADMIN = "route_to_admin"
    ESCALATE = "escalate"


@dataclass
class ApprovalPolicy:
    """
    Configurable approval routing policy.

    Maps risk scores and rule triggers to approval actions. Supports
    multiple approval tiers with different thresholds.

    Usage::

        policy = ApprovalPolicy(
            policy_id="AP-01",
            mode=ApprovalMode.HYBRID,
            auto_approve_threshold=30,
            manual_approval_threshold=70,
        )
        action = policy.evaluate(risk_score=45)
    """

    policy_id: str = "default"
    name: str = "Default Approval Policy"
    mode: ApprovalMode = ApprovalMode.HYBRID

    # ---- Thresholds ----
    auto_approve_threshold: float = 30.0  # Score <= this → auto approve
    auto_reject_threshold: float = 90.0   # Score >= this → auto reject
    manual_approval_threshold: float = 70.0  # Score >= this → manual approval
    escalation_threshold: float = 85.0    # Score >= this → escalate

    # ---- Rule-specific Overrides ----
    always_manual_rules: list[str] = field(default_factory=list)
    auto_approve_rules: list[str] = field(default_factory=list)
    auto_reject_rules: list[str] = field(default_factory=list)

    # ---- Approver Configuration ----
    approver_pool: list[str] = field(default_factory=list)
    admin_pool: list[str] = field(default_factory=list)
    approval_timeout_seconds: int = 300

    # ---- Options ----
    allow_override: bool = True
    require_comment_on_reject: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def evaluate(
        self,
        risk_score: float,
        triggered_rules: Optional[list[str]] = None,
        risk_level: str = "LOW",
    ) -> ApprovalAction:
        """
        Determine the appropriate approval action based on risk score and rules.

        Args:
            risk_score: 0–100 risk score from the evaluation pipeline.
            triggered_rules: List of rule names that triggered.
            risk_level: Text risk level (LOW/MEDIUM/HIGH/CRITICAL).

        Returns:
            The ApprovalAction to take.
        """
        triggered = set(triggered_rules or [])

        # Check rule-specific overrides first
        if triggered & set(self.auto_reject_rules):
            return ApprovalAction.AUTO_REJECT
        if triggered & set(self.always_manual_rules):
            return ApprovalAction.ROUTE_TO_APPROVER

        if self.mode == ApprovalMode.AUTO:
            return (
                ApprovalAction.AUTO_APPROVE
                if risk_score < self.manual_approval_threshold
                else ApprovalAction.AUTO_REJECT
            )

        if self.mode == ApprovalMode.MANUAL:
            return ApprovalAction.ROUTE_TO_APPROVER

        if self.mode == ApprovalMode.FOUR_EYES:
            if risk_score < self.auto_approve_threshold:
                return ApprovalAction.ROUTE_TO_APPROVER
            return ApprovalAction.ROUTE_TO_ADMIN

        # HYBRID mode (default)
        if risk_score <= self.auto_approve_threshold:
            return ApprovalAction.AUTO_APPROVE
        if risk_score >= self.auto_reject_threshold:
            return ApprovalAction.AUTO_REJECT
        if risk_score >= self.escalation_threshold:
            return ApprovalAction.ESCALATE
        if risk_score >= self.manual_approval_threshold:
            return ApprovalAction.ROUTE_TO_APPROVER

        # Moderate risk in auto range
        return ApprovalAction.AUTO_APPROVE

    def to_dict(self) -> dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "name": self.name,
            "mode": self.mode.value,
            "auto_approve_threshold": self.auto_approve_threshold,
            "auto_reject_threshold": self.auto_reject_threshold,
            "manual_approval_threshold": self.manual_approval_threshold,
            "escalation_threshold": self.escalation_threshold,
            "approval_timeout_seconds": self.approval_timeout_seconds,
        }
