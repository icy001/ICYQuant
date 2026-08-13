"""Commit 28 Part 1.4 — Approval Quorum.

``min_approvers = 2`` is not enough on its own: two approvals can come
from the *same role* (e.g. two OPERATORs approving ``trading:kill``),
which does not satisfy real separation of duties.

A :class:`QuorumRule` therefore also supports:

    distinct_principals — the approvals must come from distinct people
    required_roles      — the approving principals must collectively cover
                          every required role
    distinct_roles      — the approvals must additionally come from
                          distinct roles (split quorum, e.g.
                          Incident Commander + Risk Operator)

Evaluation:

    QuorumEvaluator.evaluate(decisions, approver_roles, rule) -> bool

where ``decisions`` are :class:`ApprovalDecision` objects and
``approver_roles`` maps approver_id -> tuple of role ids.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Mapping, Sequence

if TYPE_CHECKING:
    from .approval import ApprovalDecision


@dataclass(frozen=True)
class QuorumRule:
    """The quorum requirements for a critical approval."""

    minimum: int
    distinct_principals: bool = True
    required_roles: tuple[str, ...] = ()
    distinct_roles: bool = False


class QuorumEvaluator:
    """Deterministically evaluates whether a set of approval decisions
    satisfies a :class:`QuorumRule`."""

    def evaluate(
        self,
        decisions: Sequence["ApprovalDecision"],
        approver_roles: Mapping[str, Sequence[str]],
        rule: QuorumRule,
    ) -> bool:
        approver_roles = approver_roles or {}

        approved = [d for d in decisions if d.approved]

        if len(approved) < rule.minimum:
            return False

        principals = {d.approver_id for d in approved}
        if rule.distinct_principals and len(principals) < rule.minimum:
            return False

        if rule.required_roles:
            matched_roles = set()
            for decision in approved:
                matched_roles.update(approver_roles.get(decision.approver_id, ()))
            if not all(role in matched_roles for role in rule.required_roles):
                return False

        if rule.distinct_roles:
            role_groups = set()
            for decision in approved:
                for role in approver_roles.get(decision.approver_id, ()):
                    if role in rule.required_roles:
                        role_groups.add(role)
            if len(role_groups) < rule.minimum:
                return False

        return True
