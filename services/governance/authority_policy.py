"""
Authority Policy — policy-level authority rules.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Dict, List, Optional

from .decision_context import DecisionContext
from .decision_request import DecisionRequest


class AuthorityLevel(IntEnum):
    """Autonomy levels for actors."""

    MANUAL = 0                  # Fully manual
    RECOMMENDATION = 1          # Can recommend
    AUTO_REBALANCE = 2          # Can auto-rebalance within limits
    AUTONOMOUS_ALLOCATION = 3   # Can autonomously allocate
    EMERGENCY_RISK_CONTROL = 4  # Emergency risk control


@dataclass
class AuthorityPolicy:
    """A policy defining what authority levels can do what."""

    policy_id: str = field(default_factory=lambda: f"AUTH-{uuid.uuid4().hex[:8]}")
    name: str = ""
    description: str = ""
    enabled: bool = True

    # Which actors/levels this applies to
    actors: List[str] = field(default_factory=list)
    min_level: AuthorityLevel = AuthorityLevel.MANUAL
    max_level: AuthorityLevel = AuthorityLevel.EMERGENCY_RISK_CONTROL

    # Permissions
    allowed_decision_types: List[str] = field(default_factory=list)
    denied_decision_types: List[str] = field(default_factory=list)

    # Limits
    max_amount: float = float("inf")
    max_risk: float = float("inf")
    require_approval_above: Optional[float] = None

    # Emergency
    emergency_only: bool = False

    def evaluate(
        self, request: DecisionRequest, context: DecisionContext
    ) -> "AuthorityEvaluationResult":
        """Evaluate this policy against a request."""
        # Import here to avoid circular
        from .authority_engine import AuthorityEvaluationResult

        if not self.enabled:
            return AuthorityEvaluationResult(authorized=True, reason="Policy disabled")

        # Check actor
        if self.actors and request.actor not in self.actors:
            return AuthorityEvaluationResult(authorized=True,
                                              reason=f"Actor {request.actor} not in policy scope")

        # Check autonomy level
        actor_level = context.actor_autonomy_level
        if actor_level < self.min_level or actor_level > self.max_level:
            return AuthorityEvaluationResult(
                authorized=False,
                reason=f"Autonomy level {actor_level} not in [{self.min_level}, {self.max_level}]",
            )

        # Check emergency only
        if self.emergency_only and not context.emergency_mode:
            return AuthorityEvaluationResult(
                authorized=False,
                reason="This authority is emergency-only",
            )

        # Check allowed types
        if self.allowed_decision_types:
            if request.decision_type.name not in self.allowed_decision_types:
                return AuthorityEvaluationResult(
                    authorized=False,
                    reason=f"Decision type {request.decision_type.name} not allowed",
                )

        # Check denied types
        if self.denied_decision_types:
            if request.decision_type.name in self.denied_decision_types:
                return AuthorityEvaluationResult(
                    authorized=False,
                    reason=f"Decision type {request.decision_type.name} is denied",
                )

        # Check amount
        if request.requested_amount and request.requested_amount > self.max_amount:
            return AuthorityEvaluationResult(
                authorized=False,
                review_required=True,
                reason=f"Amount {request.requested_amount} exceeds max {self.max_amount}",
                max_amount_allowed=self.max_amount,
            )

        # Check risk
        if request.additional_risk and request.additional_risk > self.max_risk:
            return AuthorityEvaluationResult(
                authorized=False,
                review_required=True,
                reason=f"Risk {request.additional_risk} exceeds max {self.max_risk}",
                max_risk_allowed=self.max_risk,
            )

        # Check approval threshold
        if self.require_approval_above and request.requested_amount:
            if request.requested_amount > self.require_approval_above:
                return AuthorityEvaluationResult(
                    authorized=False,
                    review_required=True,
                    reason=(f"Amount {request.requested_amount} exceeds approval threshold "
                            f"{self.require_approval_above}"),
                )

        return AuthorityEvaluationResult(authorized=True, reason="Policy allows")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "name": self.name,
            "description": self.description,
            "enabled": self.enabled,
            "actors": self.actors,
            "min_level": self.min_level.name,
            "max_level": self.max_level.name,
            "allowed_decision_types": self.allowed_decision_types,
            "denied_decision_types": self.denied_decision_types,
            "max_amount": self.max_amount,
            "max_risk": self.max_risk,
            "require_approval_above": self.require_approval_above,
            "emergency_only": self.emergency_only,
        }
