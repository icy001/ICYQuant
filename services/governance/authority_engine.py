"""
Authority Engine — manages who can do what, at what scope.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from .authority_policy import AuthorityPolicy, AuthorityLevel
from .decision_authority import DecisionAuthority
from .decision_context import DecisionContext
from .decision_request import DecisionRequest


@dataclass
class AuthorityEvaluationResult:
    """Result of authority check."""

    authorized: bool = False
    review_required: bool = False
    reason: str = ""
    level: AuthorityLevel = AuthorityLevel.MANUAL
    max_amount_allowed: float = float("inf")
    max_risk_allowed: float = float("inf")
    detail: Dict[str, Any] = field(default_factory=dict)


class AuthorityEngine:
    """
    Manages actor permissions for decision types.
    Implements role-based authority with scope and autonomy level awareness.
    """

    def __init__(self, authorities: Optional[List[DecisionAuthority]] = None):
        # Key: (actor, decision_type) -> DecisionAuthority
        self._authorities: Dict[str, Dict[str, DecisionAuthority]] = {}
        self._policies: List[AuthorityPolicy] = []

        for auth in (authorities or []):
            self.grant(auth.actor, auth.decision_type, True,
                       max_amount=auth.max_amount,
                       max_risk=auth.max_risk,
                       scope=auth.scope,
                       autonomy_level=auth.autonomy_level,
                       approval_required=auth.approval_required)

    # ------------------------------------------------------------------
    # Authority management
    # ------------------------------------------------------------------

    def grant(
        self,
        actor: str,
        decision_type: str,
        authorized: bool = True,
        max_amount: float = float("inf"),
        max_risk: float = float("inf"),
        scope: str = "GLOBAL",
        autonomy_level: AuthorityLevel = AuthorityLevel.RECOMMENDATION,
        approval_required: bool = False,
        conditions: Optional[Dict[str, Any]] = None,
    ) -> DecisionAuthority:
        """Grant authority to an actor for a decision type."""
        authority = DecisionAuthority(
            actor=actor,
            decision_type=decision_type,
            authorized=authorized,
            max_amount=max_amount,
            max_risk=max_risk,
            scope=scope,
            autonomy_level=autonomy_level,
            approval_required=approval_required,
            conditions=conditions or {},
        )

        if actor not in self._authorities:
            self._authorities[actor] = {}
        self._authorities[actor][decision_type] = authority
        return authority

    def revoke(self, actor: str, decision_type: str) -> None:
        """Revoke authority."""
        if actor in self._authorities:
            self._authorities[actor].pop(decision_type, None)

    def get_authority(self, actor: str, decision_type: str) -> Optional[DecisionAuthority]:
        """Get authority for a specific actor + decision type."""
        actor_auths = self._authorities.get(actor, {})
        # Exact match first
        if decision_type in actor_auths:
            return actor_auths[decision_type]
        # Wildcard match
        if "*" in actor_auths:
            return actor_auths["*"]
        return None

    def list_authorities(self, actor: Optional[str] = None) -> List[DecisionAuthority]:
        """List authorities, optionally filtered by actor."""
        result = []
        for act, auths in self._authorities.items():
            if actor and act != actor:
                continue
            result.extend(auths.values())
        return result

    # ------------------------------------------------------------------
    # Policy management
    # ------------------------------------------------------------------

    def add_policy(self, policy: AuthorityPolicy) -> None:
        self._policies.append(policy)

    def remove_policy(self, policy_id: str) -> None:
        self._policies = [p for p in self._policies if p.policy_id != policy_id]

    # ------------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------------

    def evaluate(
        self, request: DecisionRequest, context: DecisionContext
    ) -> AuthorityEvaluationResult:
        """Check whether an actor has authority for a decision."""
        decision_type = request.decision_type.name
        actor = request.actor

        authority = self.get_authority(actor, decision_type)

        # Check policies
        result = self._evaluate_policies(request, context)

        if authority is None:
            # No explicit authority → check if any policy applies
            if not result.authorized:
                return AuthorityEvaluationResult(
                    authorized=False,
                    reason=f"No authority for {actor} to perform {decision_type}",
                    level=AuthorityLevel.MANUAL,
                )
            return result

        if not authority.authorized:
            return AuthorityEvaluationResult(
                authorized=False,
                reason=f"Actor {actor} is explicitly denied for {decision_type}",
                level=authority.autonomy_level,
            )

        # Check amount
        if request.requested_amount and request.requested_amount > authority.max_amount:
            return AuthorityEvaluationResult(
                authorized=False,
                review_required=True,
                reason=(f"Requested amount {request.requested_amount} exceeds "
                        f"max {authority.max_amount} for {actor}"),
                level=authority.autonomy_level,
                max_amount_allowed=authority.max_amount,
                max_risk_allowed=authority.max_risk,
            )

        # Check risk
        if request.additional_risk and request.additional_risk > authority.max_risk:
            return AuthorityEvaluationResult(
                authorized=False,
                review_required=True,
                reason=(f"Requested risk {request.additional_risk} exceeds "
                        f"max {authority.max_risk} for {actor}"),
                level=authority.autonomy_level,
                max_amount_allowed=authority.max_amount,
                max_risk_allowed=authority.max_risk,
            )

        # Check autonomy level
        if context.actor_autonomy_level > 0:
            if context.actor_autonomy_level < authority.autonomy_level.value:
                return AuthorityEvaluationResult(
                    authorized=False,
                    review_required=True,
                    reason=(f"Autonomy level {context.actor_autonomy_level} insufficient "
                            f"(need {authority.autonomy_level.value})"),
                    level=authority.autonomy_level,
                    max_amount_allowed=authority.max_amount,
                    max_risk_allowed=authority.max_risk,
                )

        # Check approval requirement
        if authority.approval_required:
            return AuthorityEvaluationResult(
                authorized=True,
                review_required=True,
                reason="Approval required for this authority level",
                level=authority.autonomy_level,
                max_amount_allowed=authority.max_amount,
                max_risk_allowed=authority.max_risk,
            )

        # Check conditions
        if authority.conditions:
            if not self._check_conditions(authority.conditions, context):
                return AuthorityEvaluationResult(
                    authorized=False,
                    reason="Authority conditions not met",
                    level=authority.autonomy_level,
                )

        return AuthorityEvaluationResult(
            authorized=True,
            level=authority.autonomy_level,
            max_amount_allowed=authority.max_amount,
            max_risk_allowed=authority.max_risk,
            reason="Authorized",
        )

    # ------------------------------------------------------------------
    # Built-in actor setup
    # ------------------------------------------------------------------

    def setup_default_authorities(self) -> None:
        """Register default ICYQuant actor authorities."""
        # SYSTEM — full autonomous operations within policy
        self.grant("SYSTEM", "CAPITAL_ALLOCATION", True,
                   max_amount=50_000_000, autonomy_level=AuthorityLevel.AUTONOMOUS_ALLOCATION)
        self.grant("SYSTEM", "CAPITAL_REBALANCE", True,
                   max_amount=50_000_000, autonomy_level=AuthorityLevel.AUTONOMOUS_ALLOCATION)
        self.grant("SYSTEM", "RISK_BUDGET_CHANGE", True,
                   max_risk=2_000_000, autonomy_level=AuthorityLevel.AUTONOMOUS_ALLOCATION)
        self.grant("SYSTEM", "ORDER_SUBMIT", True,
                   max_amount=10_000_000, autonomy_level=AuthorityLevel.AUTO_REBALANCE)
        self.grant("SYSTEM", "EMERGENCY_ACTION", True,
                   autonomy_level=AuthorityLevel.EMERGENCY_RISK_CONTROL)

        # RISK_ENGINE — can reduce risk, cannot increase
        self.grant("RISK_ENGINE", "RISK_BUDGET_CHANGE", True,
                   max_risk=5_000_000, autonomy_level=AuthorityLevel.EMERGENCY_RISK_CONTROL)
        self.grant("RISK_ENGINE", "LEVERAGE_CHANGE", True,
                   autonomy_level=AuthorityLevel.EMERGENCY_RISK_CONTROL)
        self.grant("RISK_ENGINE", "EMERGENCY_ACTION", True,
                   autonomy_level=AuthorityLevel.EMERGENCY_RISK_CONTROL)

        # STRATEGY — can only make recommendations
        self.grant("STRATEGY", "ORDER_SUBMIT", True,
                   max_amount=1_000_000, autonomy_level=AuthorityLevel.RECOMMENDATION,
                   approval_required=True)

        # PORTFOLIO_MANAGER — can rebalance within limits
        self.grant("PORTFOLIO_MANAGER", "CAPITAL_REBALANCE", True,
                   max_amount=20_000_000, autonomy_level=AuthorityLevel.AUTO_REBALANCE,
                   approval_required=False)
        self.grant("PORTFOLIO_MANAGER", "ORDER_SUBMIT", True,
                   max_amount=5_000_000, autonomy_level=AuthorityLevel.AUTO_REBALANCE)

        # ADMIN — override
        self.grant("ADMIN", "*", True,
                   max_amount=float("inf"), autonomy_level=AuthorityLevel.MANUAL,
                   approval_required=False)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _evaluate_policies(self, request: DecisionRequest,
                           context: DecisionContext) -> AuthorityEvaluationResult:
        """Evaluate authority policies."""
        for policy in self._policies:
            if not policy.enabled:
                continue
            result = policy.evaluate(request, context)
            if not result.authorized:
                return result
        return AuthorityEvaluationResult(authorized=True, reason="No policies block")

    @staticmethod
    def _check_conditions(conditions: Dict[str, Any], context: DecisionContext) -> bool:
        """Check authority conditions against context."""
        for key, expected in conditions.items():
            actual = getattr(context, key, None)
            if actual != expected:
                return False
        return True
