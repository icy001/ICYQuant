"""Decision — governance context, decision model and engine (Commit 28 Part 1.1).

一次请求不再只有 True / False，而是：
    ALLOW / DENY / REQUIRE_APPROVAL

GovernanceEngine 是本 Part 的基础骨架：
    Principal -> Active? -> Role -> Permission -> Policy -> Decision

原则（Commit 28 Part 1.1, section 38）：
    - Default Deny：无明确授权即拒绝。
    - Fail Closed：引擎异常时拒绝（或进入显式 Emergency Safety Policy）。
    - Permission != Authorization：有权限不等于当前一定允许。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .registry import GovernanceRegistry


class DecisionEffect(str, Enum):
    """The effect of a governance decision."""

    ALLOW = "ALLOW"
    DENY = "DENY"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"


@dataclass(frozen=True)
class GovernanceContext:
    """Request context evaluated by the governance engine.

    Captures WHO (principal + roles), WHAT (resource + action),
    WHERE (environment), WHY (incident/severity) and approval state.
    """

    principal_id: str
    role_ids: tuple[str, ...]
    resource: str
    action: str
    environment: str
    incident_id: str | None = None
    severity: str | None = None
    approval_id: str | None = None


@dataclass(frozen=True)
class GovernanceDecision:
    """The outcome of a governance evaluation."""

    effect: DecisionEffect
    reason: str
    policy_id: str | None = None
    approval_required: bool = False


class GovernanceEngine:
    """Production governance decision engine (Part 1.1 skeleton).

    REQUIRES_APPROVAL / condition evaluation is added by the next
    commit part (Policy Evaluation Engine); this part fixes the
    Principal / Permission / Policy chain with Default Deny and
    Fail Closed semantics.
    """

    def __init__(self, registry: GovernanceRegistry | None = None) -> None:
        self._registry = registry if registry is not None else GovernanceRegistry()

    @property
    def registry(self) -> GovernanceRegistry:
        return self._registry

    def evaluate(self, context: GovernanceContext) -> GovernanceDecision:
        """Evaluate a request context. Never raises: fails closed on error."""
        try:
            return self._evaluate(context)
        except Exception:
            return GovernanceDecision(
                effect=DecisionEffect.DENY,
                reason="governance failure: fail closed",
            )

    def _evaluate(self, context: GovernanceContext) -> GovernanceDecision:
        if not context.principal_id:
            return GovernanceDecision(
                effect=DecisionEffect.DENY,
                reason="principal required",
            )

        principal = self._registry.get_principal(context.principal_id)
        if principal is None:
            return GovernanceDecision(
                effect=DecisionEffect.DENY,
                reason="principal not found",
            )
        if not principal.active:
            return GovernanceDecision(
                effect=DecisionEffect.DENY,
                reason="principal inactive",
            )

        if not self._has_permission(context):
            return GovernanceDecision(
                effect=DecisionEffect.DENY,
                reason="permission denied",
            )

        policies = self._registry.policies_for(context.resource, context.action)
        if not policies:
            return GovernanceDecision(
                effect=DecisionEffect.DENY,
                reason="no policy matched",
            )

        best = policies[0]
        return GovernanceDecision(
            effect=DecisionEffect.ALLOW,
            reason="policy matched",
            policy_id=best.policy_id,
        )

    def _has_permission(self, context: GovernanceContext) -> bool:
        for role_id in context.role_ids:
            for permission_id in self._registry.permissions_for_role(role_id):
                permission = self._registry.get_permission(permission_id)
                if permission is None:
                    continue
                if (
                    permission.resource == context.resource
                    and permission.action == context.action
                ):
                    return True
        return False
