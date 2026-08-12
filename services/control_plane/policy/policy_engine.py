"""
PolicyEngine — deterministic operational policy evaluation.

Pipeline:

    State Snapshot (PolicyContext)
        → load applicable policies
        → evaluate conditions (pure)
        → resolve priority (fail-safe ordering)
        → generate decision
        → generate actions
        → PolicyEvaluation (audited)

Safety-first conflict resolution:

    ALLOW < DEGRADE < RECOVER < BLOCK < HALT < ESCALATE

The engine never decides "maybe" — every evaluation produces exactly one
decision, one priority, a list of requested actions, and the full audit trail
(matched policies, versions, rules, reasons, correlation id).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence

from .policy import Policy as _Policy  # local alias to avoid confusion
from .policy_action import PolicyAction
from .policy_context import PolicyContext
from .policy_decision import PolicyDecision, most_severe
from .policy_priority import PolicyPriority, highest_priority

Policy = _Policy


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# manual override
# ---------------------------------------------------------------------------


class OverrideScope(str, Enum):
    """Scope of a manual override request."""

    GLOBAL = "GLOBAL"
    ACCOUNT = "ACCOUNT"
    STRATEGY = "STRATEGY"
    INSTRUMENT = "INSTRUMENT"
    VENUE = "VENUE"


@dataclass
class ManualOverride:
    """
    A manual override is never "admin says allow, so allow".

    It only becomes effective after the full chain:

        Request → Authorization → Policy Validation → Approval → Override

    A GLOBAL override can never lift a HALT / ESCALATE decision back to ALLOW
    — the fail-safe boundary cannot be bypassed.
    """

    scope: OverrideScope
    scope_id: str = ""
    requested_by: str = ""
    reason: str = ""
    authorized: bool = False
    approved: bool = False
    policy_valid: bool = False

    def is_effective(self) -> bool:
        """All of authorization, approval and policy validation must hold."""
        return self.authorized and self.approved and self.policy_valid

    def can_override(self, decision: PolicyDecision) -> bool:
        """Whether this override may lift ``decision`` for its scope."""
        if not self.is_effective():
            return False
        # Fail-safe: GLOBAL override cannot downgrade a hard stop.
        if (
            self.scope is OverrideScope.GLOBAL
            and decision in (PolicyDecision.HALT, PolicyDecision.ESCALATE)
        ):
            return False
        return True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scope": self.scope.value,
            "scope_id": self.scope_id,
            "requested_by": self.requested_by,
            "reason": self.reason,
            "authorized": self.authorized,
            "approved": self.approved,
            "policy_valid": self.policy_valid,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ManualOverride":
        return cls(
            scope=OverrideScope(data["scope"]),
            scope_id=data.get("scope_id", ""),
            requested_by=data.get("requested_by", ""),
            reason=data.get("reason", ""),
            authorized=data.get("authorized", False),
            approved=data.get("approved", False),
            policy_valid=data.get("policy_valid", False),
        )


# ---------------------------------------------------------------------------
# evaluation result
# ---------------------------------------------------------------------------


@dataclass
class PolicyEvaluation:
    """Full result of one engine evaluation — the audit record."""

    decision: PolicyDecision
    priority: PolicyPriority
    actions: List[PolicyAction]
    matched_policies: List[str]
    policy_versions: Dict[str, str]
    matched_rules: List[str]
    reasons: List[str]
    context: PolicyContext
    evaluated_at: datetime
    correlation_id: str = ""

    @property
    def is_allowed(self) -> bool:
        return self.decision is PolicyDecision.ALLOW

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision": self.decision.value,
            "priority": self.priority.value,
            "actions": [a.to_dict() for a in self.actions],
            "matched_policies": list(self.matched_policies),
            "policy_versions": dict(self.policy_versions),
            "matched_rules": list(self.matched_rules),
            "reasons": list(self.reasons),
            "context": self.context.to_dict(),
            "evaluated_at": self.evaluated_at.isoformat(),
            "correlation_id": self.correlation_id,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PolicyEvaluation":
        return cls(
            decision=PolicyDecision(data["decision"]),
            priority=PolicyPriority(data["priority"]),
            actions=[PolicyAction.from_dict(a) for a in data.get("actions", [])],
            matched_policies=list(data.get("matched_policies", [])),
            policy_versions=dict(data.get("policy_versions", {})),
            matched_rules=list(data.get("matched_rules", [])),
            reasons=list(data.get("reasons", [])),
            context=PolicyContext.from_dict(data["context"]),
            evaluated_at=datetime.fromisoformat(data["evaluated_at"]),
            correlation_id=data.get("correlation_id", ""),
        )


# ---------------------------------------------------------------------------
# engine
# ---------------------------------------------------------------------------


class PolicyEngine:
    """Deterministic evaluator over a registry of Policies."""

    def __init__(
        self,
        policies: Optional[Sequence[Policy]] = None,
        repository: Any = None,
    ) -> None:
        self._policies: List[Policy] = list(policies or [])
        self._by_id: Dict[str, Policy] = {p.policy_id: p for p in self._policies}
        self._repository = repository

    # -- registry ---------------------------------------------------------

    def register_policy(self, policy: Policy) -> None:
        if not isinstance(policy, Policy):
            raise TypeError(f"expected Policy, got {type(policy).__name__}")
        if policy.policy_id in self._by_id:
            raise ValueError(
                f"policy {policy.policy_id!r} is already registered"
            )
        self._policies.append(policy)
        self._by_id[policy.policy_id] = policy

    def register_policies(self, *policies: Policy) -> None:
        for policy in policies:
            self.register_policy(policy)

    def unregister_policy(self, policy_id: str) -> bool:
        policy = self._by_id.pop(policy_id, None)
        if policy is None:
            return False
        self._policies = [p for p in self._policies if p.policy_id != policy_id]
        return True

    def get_policy(self, policy_id: str) -> Optional[Policy]:
        return self._by_id.get(policy_id)

    def list_policies(self) -> List[Policy]:
        return list(self._policies)

    @property
    def policy_count(self) -> int:
        return len(self._policies)

    # -- evaluation -------------------------------------------------------

    def evaluate(
        self,
        context: PolicyContext,
        at: Optional[datetime] = None,
        correlation_id: str = "",
    ) -> PolicyEvaluation:
        """
        Evaluate all registered policies against ``context``.

        Deterministic: for the same context, the same registered policies and
        the same correlation id, the result is always identical.
        """
        if not isinstance(context, PolicyContext):
            raise TypeError(
                f"expected PolicyContext, got {type(context).__name__}"
            )

        evaluated_at = at or _utcnow()
        effective = [p for p in self._policies if p.enabled]

        results = [policy.evaluate(context) for policy in effective]
        matched = [r for r in results if r.matched]

        if not matched:
            return PolicyEvaluation(
                decision=PolicyDecision.ALLOW,
                priority=PolicyPriority.LOW,
                actions=[],
                matched_policies=[],
                policy_versions={},
                matched_rules=[],
                reasons=[],
                context=context,
                evaluated_at=evaluated_at,
                correlation_id=correlation_id,
            )

        decisions = [r.decision for r in matched if r.decision is not None]
        final_decision = most_severe(decisions) if decisions else PolicyDecision.ALLOW

        actions: List[PolicyAction] = []
        seen = set()
        for r in matched:
            for act in r.actions:
                key = (act.action_type, act.target)
                if key not in seen:
                    seen.add(key)
                    actions.append(act)

        policy_versions = {
            r.policy_id: r.policy_version for r in matched
        }
        matched_rules: List[str] = []
        for r in matched:
            matched_rules.extend(r.matched_rules)

        reasons: List[str] = []
        for r in matched:
            for reason in r.reasons:
                if reason not in reasons:
                    reasons.append(reason)

        return PolicyEvaluation(
            decision=final_decision,
            priority=highest_priority(
                [r.priority for r in matched if r.priority is not None]
            ),
            actions=actions,
            matched_policies=[r.policy_id for r in matched],
            policy_versions=policy_versions,
            matched_rules=matched_rules,
            reasons=reasons,
            context=context,
            evaluated_at=evaluated_at,
            correlation_id=correlation_id,
        )

    def decision_for(
        self, context: PolicyContext, correlation_id: str = ""
    ) -> PolicyDecision:
        """Convenience — return only the decision."""
        return self.evaluate(context, correlation_id=correlation_id).decision

    # -- persistence hook -------------------------------------------------

    def record_evaluation(self, evaluation: PolicyEvaluation) -> None:
        """Persist the evaluation via the attached repository (if any)."""
        if self._repository is not None:
            self._repository.record_evaluation(evaluation)
