"""Approval — governance approval model (Commit 28 Part 1.1, Part 1.3).

Part 1.1 定义了 Approval 对象；Part 1.3 把它升级为真正的状态机：

    CREATE -> PENDING -> {APPROVED, REJECTED, EXPIRED}
    APPROVED -> CONSUMED

不变量（Four-Eyes / Separation of Duties）：
    - Requester != Approver：提出操作的人不能批准自己的操作。
    - 终态（APPROVED / REJECTED / EXPIRED / CONSUMED）不可再次修改。
    - Approval 是 single-use：消费（CONSUMED）之后不能重放。
    - Rejection 必须携带 reason，供 Audit 回答"为什么没有批准"。

与 Commit 27 的 Runbook Approval 区分：
    Runbook Approval   解决"事故处理流程中的某一步需要批准"。
    Governance Approval 解决"组织层面的权限和政策是否允许这次批准"。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .approval_rule import ApprovalRule


class ApprovalState(str, Enum):
    """Lifecycle states of a governance approval."""

    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    CONSUMED = "CONSUMED"


@dataclass(frozen=True)
class Approval:
    """A governance approval for a resource+action request."""

    approval_id: str
    resource: str
    action: str
    requested_by: str
    state: ApprovalState = ApprovalState.PENDING
    incident_id: str | None = None
    requested_at: datetime | None = None
    expires_at: datetime | None = None
    approved_by: str | None = None
    approved_at: datetime | None = None
    rejection_reason: str | None = None
    policy_id: str | None = None


def validate_approver(approval: Approval, approver_id: str) -> None:
    """Four-eyes invariant: the requester can never approve their own request.

    This rule cannot be overridden by any ordinary Policy.
    """
    if approval.requested_by == approver_id:
        raise PermissionError("requester cannot approve own request")


def validate_binding(
    approval: Approval,
    resource: str,
    action: str,
    incident_id: str | None = None,
    requester: str | None = None,
    policy_id: str | None = None,
) -> None:
    """An approval is bound to the exact resource+action it was created for.

    APR-001 approved for ``trading:resume`` can never be used to authorize
    ``trading:kill`` (or another incident / requester / policy).
    """
    if approval.resource != resource or approval.action != action:
        raise ValueError("approval binding mismatch")

    if incident_id is not None and approval.incident_id != incident_id:
        raise ValueError("approval binding mismatch: incident")

    if requester is not None and approval.requested_by != requester:
        raise ValueError("approval binding mismatch: requester")

    if policy_id is not None and approval.policy_id != policy_id:
        raise ValueError("approval binding mismatch: policy")


def approve(
    approval: Approval,
    approver_id: str,
    now: datetime,
) -> Approval:
    """PENDING -> APPROVED.

    Raises ValueError when the approval is not pending or has expired,
    and PermissionError on self-approval.
    """
    if approval.state != ApprovalState.PENDING:
        raise ValueError("approval is not pending")

    if approval.expires_at is not None and now >= approval.expires_at:
        raise ValueError("approval expired")

    if approval.requested_by == approver_id:
        raise PermissionError("self approval forbidden")

    return Approval(
        approval_id=approval.approval_id,
        incident_id=approval.incident_id,
        resource=approval.resource,
        action=approval.action,
        requested_by=approval.requested_by,
        requested_at=approval.requested_at,
        expires_at=approval.expires_at,
        state=ApprovalState.APPROVED,
        approved_by=approver_id,
        approved_at=now,
        policy_id=approval.policy_id,
    )


def reject(
    approval: Approval,
    approver_id: str,
    reason: str,
) -> Approval:
    """PENDING -> REJECTED.

    Rejection always requires a reason: the audit trail must answer
    "why was this not approved?". Self-rejection is forbidden.
    """
    if approval.state != ApprovalState.PENDING:
        raise ValueError("approval is not pending")

    if approval.requested_by == approver_id:
        raise PermissionError("requester cannot reject own request")

    if not reason:
        raise ValueError("rejection reason required")

    return Approval(
        approval_id=approval.approval_id,
        incident_id=approval.incident_id,
        resource=approval.resource,
        action=approval.action,
        requested_by=approval.requested_by,
        requested_at=approval.requested_at,
        expires_at=approval.expires_at,
        state=ApprovalState.REJECTED,
        rejection_reason=reason,
        policy_id=approval.policy_id,
    )


def expire_approval(
    approval: Approval,
    now: datetime | None = None,
) -> Approval:
    """PENDING -> EXPIRED. A terminal state: it can never be approved later."""
    if approval.state != ApprovalState.PENDING:
        raise ValueError("approval is not pending")

    return Approval(
        approval_id=approval.approval_id,
        incident_id=approval.incident_id,
        resource=approval.resource,
        action=approval.action,
        requested_by=approval.requested_by,
        requested_at=approval.requested_at,
        expires_at=approval.expires_at,
        state=ApprovalState.EXPIRED,
        policy_id=approval.policy_id,
    )


def consume(approval: Approval) -> Approval:
    """APPROVED -> CONSUMED.

    An approval is single-use. Consuming marks it used so it cannot be
    replayed against a later control request.
    """
    if approval.state != ApprovalState.APPROVED:
        raise ValueError("approval must be approved before consumption")

    return Approval(
        approval_id=approval.approval_id,
        incident_id=approval.incident_id,
        resource=approval.resource,
        action=approval.action,
        requested_by=approval.requested_by,
        requested_at=approval.requested_at,
        expires_at=approval.expires_at,
        state=ApprovalState.CONSUMED,
        approved_by=approval.approved_by,
        approved_at=approval.approved_at,
        policy_id=approval.policy_id,
    )


@dataclass(frozen=True)
class ApprovalDecision:
    """One approver's decision on an approval request.

    An approval request may carry multiple decisions; the aggregator
    combines them against the ApprovalRule.
    """

    approval_id: str
    approver_id: str
    approved: bool
    timestamp: datetime
    reason: str | None = None
    approver_roles: tuple[str, ...] = ()


class ApprovalAggregator:
    """Aggregates approval decisions against an ApprovalRule.

    - Any rejection rejects the whole request (REJECTED).
    - Duplicate approvers count once: ``unique_approvers``.
    - ``min_approvers`` distinct approvers are required, otherwise PENDING.
    - ``distinct_roles_required`` (optional) additionally requires the
      approvals to come from distinct roles.
    """

    def evaluate(
        self,
        decisions: list[ApprovalDecision],
        rule: ApprovalRule,
    ) -> ApprovalState:
        rejected = any(not decision.approved for decision in decisions)
        if rejected:
            return ApprovalState.REJECTED

        unique_approvers = {decision.approver_id for decision in decisions}

        if len(unique_approvers) < rule.min_approvers:
            return ApprovalState.PENDING

        if rule.distinct_roles_required:
            unique_roles = {
                role
                for decision in decisions
                for role in getattr(decision, "approver_roles", ())
            }
            if len(unique_roles) < rule.min_approvers:
                return ApprovalState.PENDING

        return ApprovalState.APPROVED
