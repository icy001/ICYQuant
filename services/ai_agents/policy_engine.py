"""
ICYQuant Policy Engine — policy-based action gating for AI agents.

Enforces organizational and regulatory policies on AI agent actions.
Policies define what agents are allowed, required, and forbidden to do.
All policy violations are logged for audit.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class PolicyEffect(str, Enum):
    ALLOW = "allow"
    DENY = "deny"


class PolicyScope(str, Enum):
    GLOBAL = "global"            # Applies to all agents
    AGENT_TYPE = "agent_type"   # Applies to specific agent types
    AGENT = "agent"             # Applies to specific agent
    ROLE = "role"               # Applies to specific role


@dataclass
class Policy:
    """A single policy rule."""
    policy_id: str
    name: str = ""
    description: str = ""
    effect: PolicyEffect = PolicyEffect.DENY
    scope: PolicyScope = PolicyScope.GLOBAL
    scope_value: str = "*"       # All if GLOBAL, agent_type if AGENT_TYPE, etc.

    # Conditions
    actions: list[str] = field(default_factory=list)    # Actions this applies to
    resources: list[str] = field(default_factory=list)   # Resources this applies to
    conditions: dict[str, Any] = field(default_factory=dict)

    # Priority (higher = evaluated first)
    priority: int = 0

    enabled: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class PolicyEvaluation:
    """Result of policy evaluation for an action."""
    allowed: bool = True
    matched_policies: list[str] = field(default_factory=list)
    denied_by: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    evaluated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class PolicyEngine:
    """Policy-based action gating for AI agents.

    Enforces policies that define what AI agents can and cannot do.
    Policies are organized by priority and scope. DENY policies always
    take precedence over ALLOW policies (deny-by-default model).

    Key policies:
        - AI must not execute trades directly (OMS-only)
        - AI must not bypass risk engine checks
        - AI must not exceed position limits
        - AI must not access unauthorized data
        - AI must provide evidence for recommendations
        - AI actions must be logged for audit
    """

    def __init__(self) -> None:
        self._policies: list[Policy] = []
        self._total_evaluations = 0
        self._total_denials = 0

        # Register built-in immutable policies
        self._register_builtin_policies()

    def _register_builtin_policies(self) -> None:
        """Register built-in platform policies. These cannot be removed."""
        builtins = [
            Policy(
                policy_id="policy_no_direct_trading",
                name="No Direct Trading by AI",
                description="AI agents must never directly execute trades. All orders go through OMS.",
                effect=PolicyEffect.DENY,
                scope=PolicyScope.GLOBAL,
                actions=["execute_trade", "place_order", "submit_order", "cancel_order"],
                priority=1000,  # Highest priority
            ),
            Policy(
                policy_id="policy_risk_check_required",
                name="Risk Check Required",
                description="All strategy/trade recommendations must pass risk engine validation.",
                effect=PolicyEffect.DENY,
                scope=PolicyScope.GLOBAL,
                actions=["approve_strategy", "recommend_trade"],
                conditions={"require_risk_check": True},
                priority=900,
            ),
            Policy(
                policy_id="policy_audit_logging",
                name="Audit Logging Required",
                description="All agent actions must be logged for audit trail.",
                effect=PolicyEffect.DENY,
                scope=PolicyScope.GLOBAL,
                actions=["*"],
                conditions={"require_audit_log": True},
                priority=800,
            ),
            Policy(
                policy_id="policy_no_system_config_modification",
                name="No System Configuration Modification",
                description="AI agents cannot modify platform configuration or guardrails.",
                effect=PolicyEffect.DENY,
                scope=PolicyScope.GLOBAL,
                actions=["modify_config", "disable_guardrail", "change_risk_limits"],
                priority=1000,
            ),
            Policy(
                policy_id="policy_evidence_required",
                name="Evidence Required for Recommendations",
                description="AI recommendations must be backed by evidence.",
                effect=PolicyEffect.DENY,
                scope=PolicyScope.GLOBAL,
                actions=["publish_recommendation", "finalize_decision"],
                conditions={"require_evidence": True},
                priority=700,
            ),
            Policy(
                policy_id="policy_human_approval_trading",
                name="Human Approval for Trading",
                description="Trading actions require human approval.",
                effect=PolicyEffect.DENY,
                scope=PolicyScope.GLOBAL,
                actions=["execute_trade", "activate_strategy"],
                conditions={"require_human_approval": True},
                priority=950,
            ),
            Policy(
                policy_id="policy_reviewer_required",
                name="Peer Review Required",
                description="Strategy outputs must be reviewed before finalization.",
                effect=PolicyEffect.DENY,
                scope=PolicyScope.GLOBAL,
                actions=["finalize_strategy"],
                conditions={"require_peer_review": True},
                priority=600,
            ),
        ]

        for policy in builtins:
            self.add_policy(policy)

    # ── Policy Management ──

    def add_policy(self, policy: Policy) -> None:
        """Add a policy. Built-in policies cannot be removed."""
        self._policies.append(policy)
        self._policies.sort(key=lambda p: -p.priority)
        logger.debug("Policy added: %s [%s] priority=%d",
                      policy.policy_id, policy.effect.value, policy.priority)

    def remove_policy(self, policy_id: str) -> bool:
        """Remove a custom policy. Built-in policies are immutable."""
        for policy in self._policies:
            if policy.policy_id == policy_id:
                if policy.policy_id.startswith("policy_"):
                    logger.warning("Cannot remove built-in policy: %s", policy_id)
                    return False
                self._policies.remove(policy)
                return True
        return False

    def get_policy(self, policy_id: str) -> Optional[Policy]:
        for policy in self._policies:
            if policy.policy_id == policy_id:
                return policy
        return None

    # ── Evaluation ──

    async def evaluate(self, action: str, agent_id: str = "",
                       agent_type: str = "",
                       resources: Optional[list[str]] = None,
                       context: Optional[dict[str, Any]] = None) -> PolicyEvaluation:
        """Evaluate all policies against an action."""
        self._total_evaluations += 1
        resources = resources or []
        context = context or {}

        evaluation = PolicyEvaluation()

        for policy in self._policies:
            if not policy.enabled:
                continue

            if not self._policy_applies(policy, action, agent_id, agent_type):
                continue

            evaluation.matched_policies.append(policy.policy_id)

            if policy.effect == PolicyEffect.DENY:
                evaluation.allowed = False
                evaluation.denied_by.append(policy.policy_id)
                evaluation.reasons.append(f"{policy.name}: {policy.description}")

        if not evaluation.allowed:
            self._total_denials += 1
            logger.warning("Policy DENIED: action=%s agent=%s policies=%s",
                           action, agent_id, evaluation.denied_by)
        else:
            logger.debug("Policy ALLOWED: action=%s agent=%s", action, agent_id)

        return evaluation

    def _policy_applies(self, policy: Policy, action: str,
                        agent_id: str, agent_type: str) -> bool:
        """Check if a policy applies to the given action."""
        # Check action match
        if policy.actions and "*" not in policy.actions:
            if action not in policy.actions:
                return False

        # Check scope
        if policy.scope == PolicyScope.AGENT:
            if policy.scope_value != "*" and policy.scope_value != agent_id:
                return False
        elif policy.scope == PolicyScope.AGENT_TYPE:
            if policy.scope_value != "*" and policy.scope_value != agent_type:
                return False
        # GLOBAL applies to all

        return True

    # ── Stats ──

    @property
    def total_evaluations(self) -> int:
        return self._total_evaluations

    @property
    def total_denials(self) -> int:
        return self._total_denials

    @property
    def policy_count(self) -> int:
        return len(self._policies)
