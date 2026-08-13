"""Commit 28 Part 1.3 — Approval Rules and Approver Eligibility.

An ApprovalRule declares HOW an approval must be satisfied for a given
resource+action: the minimum number of approvers, the required roles,
whether distinct roles are needed, and the approval timeout.

Approver eligibility combines:

    Active Principal + Required Role + Different Principal = Eligible Approver

Four-Eyes invariant: the requester can never approve their own request,
regardless of any rule or policy (see ``is_eligible``).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .approval import Approval


@dataclass(frozen=True)
class ApprovalRule:
    """The rule that governs an approval request for a resource+action."""

    rule_id: str
    resource: str
    action: str
    min_approvers: int = 1
    different_approver_required: bool = True
    required_roles: tuple[str, ...] = ()
    distinct_roles_required: bool = False
    approval_timeout_seconds: int = 900

    def matches(self, resource: str, action: str) -> bool:
        """True when this rule governs the resource+action pair."""
        return self.resource == resource and self.action == action


def is_eligible(
    approver_id: str,
    approver_roles,
    approval: Approval,
    rule: ApprovalRule,
) -> bool:
    """Approver eligibility for an approval request.

    An approver is eligible only when all of the following hold:

      - an approver id is present
      - the approver is not the requester (four-eyes invariant)
      - the approver holds at least one role required by the rule
        (when the rule declares required roles)
    """
    if not approver_id:
        return False

    if approval.requested_by == approver_id:
        return False

    approver_roles = approver_roles or ()

    if rule.required_roles and not any(
        role in approver_roles for role in rule.required_roles
    ):
        return False

    return True
