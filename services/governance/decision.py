"""Decision — governance context, decision model and engine (Commit 28 Part 1.2).

一次请求不再只有 True / False，而是：
    ALLOW / DENY / REQUIRE_APPROVAL

GovernanceEngine 是确定性策略评估引擎（Part 1.2）：
    Principal -> Active? -> Permission -> Policy Match -> Conditions
    -> Priority Sort -> Conflict Resolution -> Decision

原则（Commit 28 Part 1.1/1.2）：
    - Default Deny：无明确授权即拒绝。
    - Fail Closed：引擎异常时拒绝（或进入显式 Emergency Safety Policy）。
    - Permission != Authorization：有权限不等于当前一定允许。
    - Explicit Deny > REQUIRE_APPROVAL > ALLOW。
    - Deterministic：同一 Context 必然得到同一 Decision。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from .condition import ConditionEvaluator
from .evaluator import PolicyEvaluator
from .registry import GovernanceRegistry
from .resolver import PermissionResolver


class DecisionEffect(str, Enum):
    """The effect of a governance decision."""

    ALLOW = "ALLOW"
    DENY = "DENY"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"


class ReasonCode(str, Enum):
    """Standardised governance reason codes (Commit 28 Part 1.5).

    Every decision carries a machine readable ``reason_code`` so that
    logs and ledgers never degrade to "something went wrong". A code is
    always one of:

        outcome codes    -> GOV_ALLOWED / GOV_DENIED / GOV_APPROVAL_REQUIRED
        authority codes  -> AUTHORITY_MISSING / EXPIRED / SCOPE_MISMATCH
        policy codes     -> POLICY_DENIED / POLICY_CONDITION_FAILED
        approval codes   -> APPROVAL_MISSING / EXPIRED / REJECTED / CONSUMED
        quorum codes     -> QUORUM_NOT_MET / SELF_APPROVAL_FORBIDDEN
        delegation codes -> DELEGATION_EXPIRED / DELEGATION_SCOPE_MISMATCH
        replay codes     -> REQUEST_ID_REUSE_CONFLICT /
                            POLICY_VERSION_MISMATCH / AUTHORITY_STATE_CHANGED
    """

    # Outcome
    GOV_ALLOWED = "GOV_ALLOWED"
    GOV_DENIED = "GOV_DENIED"
    GOV_APPROVAL_REQUIRED = "GOV_APPROVAL_REQUIRED"

    # Authority
    AUTHORITY_MISSING = "AUTHORITY_MISSING"
    AUTHORITY_EXPIRED = "AUTHORITY_EXPIRED"
    AUTHORITY_SCOPE_MISMATCH = "AUTHORITY_SCOPE_MISMATCH"

    # Policy
    POLICY_DENIED = "POLICY_DENIED"
    POLICY_CONDITION_FAILED = "POLICY_CONDITION_FAILED"

    # Approval
    APPROVAL_MISSING = "APPROVAL_MISSING"
    APPROVAL_EXPIRED = "APPROVAL_EXPIRED"
    APPROVAL_REJECTED = "APPROVAL_REJECTED"
    APPROVAL_CONSUMED = "APPROVAL_CONSUMED"

    # Quorum
    QUORUM_NOT_MET = "QUORUM_NOT_MET"
    SELF_APPROVAL_FORBIDDEN = "SELF_APPROVAL_FORBIDDEN"

    # Delegation
    DELEGATION_EXPIRED = "DELEGATION_EXPIRED"
    DELEGATION_SCOPE_MISMATCH = "DELEGATION_SCOPE_MISMATCH"

    # Request / Replay
    REQUEST_ID_REUSE_CONFLICT = "REQUEST_ID_REUSE_CONFLICT"
    POLICY_VERSION_MISMATCH = "POLICY_VERSION_MISMATCH"
    AUTHORITY_STATE_CHANGED = "AUTHORITY_STATE_CHANGED"


@dataclass(frozen=True)
class GovernanceContext:
    """Request context evaluated by the governance engine.

    Captures WHO (principal + roles), WHAT (resource + action),
    WHERE (environment), WHY (incident/severity), approval state and
    recovery state. Recovery fields (Commit 28 Part 1.2) let the
    engine authorise resume only after recovery completed:
        recovery_status / reconciliation_status / risk_status
    """

    principal_id: str
    role_ids: tuple[str, ...]
    resource: str
    action: str
    environment: str
    incident_id: str | None = None
    severity: str | None = None
    approval_id: str | None = None
    recovery_status: str | None = None
    reconciliation_status: str | None = None
    risk_status: str | None = None


@dataclass(frozen=True)
class GovernanceDecision:
    """The outcome of a governance evaluation.

    Commit 28 Part 1.5 extends the decision with ledger / evidence
    fields so every decision can be permanently explained, replayed,
    audited and proven: who decided, which policy, whose authority,
    which approval, when, and in what context.

    ``decision_id`` is the identity (UUID-like), ``sequence`` is the
    ledger ordering — the two have distinct responsibilities.
    """

    effect: DecisionEffect
    reason: str
    policy_id: str | None = None
    approval_required: bool = False
    # Commit 28 Part 1.5 — Decision Ledger / Evidence / Replay
    decision_id: str | None = None
    request_id: str | None = None
    principal_id: str | None = None
    resource: str | None = None
    action: str | None = None
    authority_source: str | None = None
    approval_id: str | None = None
    reason_code: str | None = None
    decided_at: datetime | None = None
    sequence: int | None = None
    context_hash: str | None = None


class GovernanceEngine:
    """Deterministic production governance decision engine (Part 1.2).

    Evaluates a GovernanceContext through:

        Principal -> Active? -> Permission -> Policy Match -> Conditions
        -> Priority Sort -> Conflict Resolution

    Policy ordering is stable: policies are sorted by
    ``(priority, policy_id)`` so the same context always yields the
    same decision regardless of registry insertion order.

    Never raises: fails closed on any engine error.
    """

    def __init__(
        self,
        registry: GovernanceRegistry | None = None,
        permission_resolver: PermissionResolver | None = None,
        policy_evaluator: PolicyEvaluator | None = None,
        condition_evaluator: ConditionEvaluator | None = None,
    ) -> None:
        self._registry = registry if registry is not None else GovernanceRegistry()
        self._condition_evaluator = condition_evaluator or ConditionEvaluator()
        self._permission_resolver = permission_resolver or PermissionResolver(
            self._registry
        )
        self._policy_evaluator = policy_evaluator or PolicyEvaluator(
            self._condition_evaluator
        )

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

        if not self._permission_resolver.has_permission(
            context.role_ids,
            context.resource,
            context.action,
        ):
            return GovernanceDecision(
                effect=DecisionEffect.DENY,
                reason="permission denied",
            )

        matched = [
            policy
            for policy in self._registry.policies.values()
            if self._policy_evaluator.matches(policy, context)
        ]

        if not matched:
            return GovernanceDecision(
                effect=DecisionEffect.DENY,
                reason="no policy matched",
            )

        matched.sort(key=lambda policy: (policy.priority, policy.policy_id))

        return self._resolve(matched)

    def _resolve(self, policies: list) -> GovernanceDecision:
        """Conflict resolution: Explicit Deny > REQUIRE_APPROVAL > ALLOW."""
        for policy in policies:
            if policy.effect == "DENY":
                return GovernanceDecision(
                    effect=DecisionEffect.DENY,
                    reason=f"denied by {policy.policy_id}",
                    policy_id=policy.policy_id,
                )

        for policy in policies:
            if policy.effect == "REQUIRE_APPROVAL":
                return GovernanceDecision(
                    effect=DecisionEffect.REQUIRE_APPROVAL,
                    reason=f"approval required by {policy.policy_id}",
                    policy_id=policy.policy_id,
                    approval_required=True,
                )

        for policy in policies:
            if policy.effect == "ALLOW":
                return GovernanceDecision(
                    effect=DecisionEffect.ALLOW,
                    reason=f"allowed by {policy.policy_id}",
                    policy_id=policy.policy_id,
                )

        return GovernanceDecision(
            effect=DecisionEffect.DENY,
            reason="no effective policy",
        )
