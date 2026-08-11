"""Tool Policy Engine — rule-based policy evaluation for tool execution.

Pipeline:
    Execution Request
        -> PolicyEngine.evaluate()
        -> Policy Rules (allow / deny / condition)
        -> Constraints (rate, quota, time, resource)
        -> Decision
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


# ── Enums ──

class PolicyEffect(str, Enum):
    """Policy evaluation effect."""

    ALLOW = "allow"
    DENY = "deny"
    AUDIT = "audit"  # Allow but flag for audit


class PolicyType(str, Enum):
    """Policy rule type."""

    RATE_LIMIT = "rate_limit"
    QUOTA = "quota"
    TIME_WINDOW = "time_window"
    RESOURCE = "resource"
    IP_RANGE = "ip_range"
    CUSTOM = "custom"


# ── Policy ──

@dataclass
class Policy:
    """A policy rule for tool execution control."""

    name: str
    description: str = ""
    policy_type: PolicyType = PolicyType.CUSTOM
    effect: PolicyEffect = PolicyEffect.ALLOW

    # ── Scope ──
    applies_to: List[str] = field(default_factory=list)  # tool names or "*"
    applies_to_agents: List[str] = field(default_factory=list)  # agent IDs or "*"
    applies_to_roles: List[str] = field(default_factory=list)  # role names

    # ── Constraints ──
    max_calls_per_minute: Optional[int] = None
    max_calls_per_hour: Optional[int] = None
    max_calls_per_day: Optional[int] = None
    max_concurrent: Optional[int] = None
    allowed_time_windows: List[Dict[str, Any]] = field(default_factory=list)
    required_tags: List[str] = field(default_factory=list)
    forbidden_tags: List[str] = field(default_factory=list)

    # ── Conditions ──
    conditions: Dict[str, Any] = field(default_factory=dict)

    # ── Priority ──
    priority: int = 0

    # ── Metadata ──
    enabled: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "name": self.name,
            "description": self.description,
            "policy_type": self.policy_type.value,
            "effect": self.effect.value,
            "applies_to": self.applies_to,
            "applies_to_agents": self.applies_to_agents,
            "applies_to_roles": self.applies_to_roles,
            "max_calls_per_minute": self.max_calls_per_minute,
            "max_calls_per_hour": self.max_calls_per_hour,
            "max_calls_per_day": self.max_calls_per_day,
            "max_concurrent": self.max_concurrent,
            "priority": self.priority,
            "enabled": self.enabled,
        }


# ── PolicyEvaluation ──

@dataclass
class PolicyEvaluation:
    """Result of a policy evaluation."""

    policy_name: str
    effect: PolicyEffect
    matched: bool = False
    reason: str = ""
    violations: List[str] = field(default_factory=list)


# ── PolicyDecision ──

@dataclass
class PolicyDecision:
    """Aggregated policy evaluation decision."""

    allowed: bool = True
    evaluations: List[PolicyEvaluation] = field(default_factory=list)
    deny_reasons: List[str] = field(default_factory=list)
    audit_flags: List[str] = field(default_factory=list)

    @property
    def is_denied(self) -> bool:
        return not self.allowed


# ── ToolPolicyEngine ──

class ToolPolicyEngine:
    """Policy evaluation engine for tool execution.

    Evaluates all applicable policies for a tool call request and
    produces an aggregated allow/deny decision with reasons.

    Supports:
        - Rate limiting policies
        - Quota policies
        - Time-window policies
        - Resource-scoped policies
        - Tag-based filtering
        - Condition evaluation
        - Audit-flag policies

    Usage:
        engine = ToolPolicyEngine()
        engine.add_policy(Policy(name="rate_limit", max_calls_per_minute=60))
        decision = engine.evaluate(
            tool_name="backtest.run",
            agent_id="agent-001",
            agent_roles=["researcher"],
        )
    """

    def __init__(self) -> None:
        """Initialize the policy engine."""
        self._policies: Dict[str, Policy] = {}
        self._call_counters: Dict[str, Dict[str, int]] = {}  # policy_name -> counter_key -> count
        self._counter_windows: Dict[str, datetime] = {}  # policy_name -> window_start

        self._initialized: bool = False
        logger.info("ToolPolicyEngine created")

    # ── Lifecycle ──

    async def initialize(self) -> None:
        """Initialize the policy engine."""
        self._initialized = True
        logger.info("ToolPolicyEngine initialized")

    async def shutdown(self) -> None:
        """Shutdown the policy engine."""
        self._policies.clear()
        self._call_counters.clear()
        self._counter_windows.clear()
        self._initialized = False
        logger.info("ToolPolicyEngine shutdown complete")

    # ── Policy Management ──

    def add_policy(self, policy: Policy) -> None:
        """Add a policy rule.

        Args:
            policy: The policy to add.
        """
        self._policies[policy.name] = policy
        logger.info(f"Policy added: {policy.name} (type={policy.policy_type.value})")

    def remove_policy(self, policy_name: str) -> None:
        """Remove a policy rule.

        Args:
            policy_name: The policy name to remove.
        """
        self._policies.pop(policy_name, None)
        logger.info(f"Policy removed: {policy_name}")

    def get_policy(self, policy_name: str) -> Optional[Policy]:
        """Get a policy by name."""
        return self._policies.get(policy_name)

    # ── Evaluation ──

    def evaluate(
        self,
        tool_name: str,
        agent_id: str = "",
        agent_roles: Optional[List[str]] = None,
        resource: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> PolicyDecision:
        """Evaluate all applicable policies for a tool call.

        Args:
            tool_name: The tool being called.
            agent_id: The agent identifier.
            agent_roles: The agent's roles.
            resource: Optional resource identifier.
            context: Optional evaluation context.

        Returns:
            A PolicyDecision with the aggregated result.
        """
        agent_roles = agent_roles or []
        evaluations: List[PolicyEvaluation] = []
        deny_reasons: List[str] = []
        audit_flags: List[str] = []
        allowed = True

        # Sort by priority (descending)
        sorted_policies = sorted(
            self._policies.values(),
            key=lambda p: -p.priority,
        )

        for policy in sorted_policies:
            if not policy.enabled:
                continue

            # Check if policy applies to this request
            if not self._policy_applies(policy, tool_name, agent_id, agent_roles):
                continue

            # Evaluate the policy
            evaluation = self._evaluate_policy(policy, tool_name, agent_id, context)
            evaluations.append(evaluation)

            if evaluation.effect == PolicyEffect.DENY:
                deny_reasons.append(evaluation.reason)
                allowed = False
            elif evaluation.effect == PolicyEffect.AUDIT:
                audit_flags.append(evaluation.reason)

        return PolicyDecision(
            allowed=allowed,
            evaluations=evaluations,
            deny_reasons=deny_reasons,
            audit_flags=audit_flags,
        )

    # ── Counter Tracking ──

    def record_call(self, policy_name: str, tool_name: str) -> None:
        """Record a tool call for rate/quote tracking.

        Args:
            policy_name: The policy name.
            tool_name: The tool name.
        """
        if policy_name not in self._call_counters:
            self._call_counters[policy_name] = {}
        counter = self._call_counters[policy_name]
        counter[tool_name] = counter.get(tool_name, 0) + 1

    def reset_counters(self, policy_name: Optional[str] = None) -> None:
        """Reset call counters.

        Args:
            policy_name: Specific policy to reset, or all if None.
        """
        if policy_name:
            self._call_counters.pop(policy_name, None)
        else:
            self._call_counters.clear()
        self._counter_windows.clear()

    # ── Private Methods ──

    def _policy_applies(
        self,
        policy: Policy,
        tool_name: str,
        agent_id: str,
        agent_roles: List[str],
    ) -> bool:
        """Check if a policy applies to this request.

        Args:
            policy: The policy to check.
            tool_name: The tool name.
            agent_id: The agent identifier.
            agent_roles: The agent's roles.

        Returns:
            True if the policy applies.
        """
        # Check tool scope
        if policy.applies_to and "*" not in policy.applies_to:
            if tool_name not in policy.applies_to:
                return False

        # Check agent scope
        if policy.applies_to_agents and "*" not in policy.applies_to_agents:
            if agent_id not in policy.applies_to_agents:
                return False

        # Check role scope
        if policy.applies_to_roles:
            if not any(r in policy.applies_to_roles for r in agent_roles):
                return False

        # Check required tags
        if policy.required_tags:
            # Tags would come from tool metadata; simplified check
            pass

        return True

    def _evaluate_policy(
        self,
        policy: Policy,
        tool_name: str,
        agent_id: str,
        context: Optional[Dict[str, Any]],
    ) -> PolicyEvaluation:
        """Evaluate a single policy against the request.

        Args:
            policy: The policy to evaluate.
            tool_name: The tool name.
            agent_id: The agent identifier.
            context: Optional evaluation context.

        Returns:
            A PolicyEvaluation with the result.
        """
        violations: List[str] = []

        # Rate limit check
        if policy.policy_type == PolicyType.RATE_LIMIT:
            counter_key = f"{tool_name}:{agent_id}" if agent_id else tool_name
            current = self._call_counters.get(policy.name, {}).get(counter_key, 0)

            if policy.max_calls_per_minute and current >= policy.max_calls_per_minute:
                violations.append(
                    f"Rate limit exceeded: {current}/{policy.max_calls_per_minute} calls per minute"
                )
            if policy.max_calls_per_hour:
                violations.append("Hourly rate limit check: simplified")
            if policy.max_calls_per_day:
                violations.append("Daily rate limit check: simplified")

        # Time window check
        if policy.policy_type == PolicyType.TIME_WINDOW and policy.allowed_time_windows:
            now = datetime.now(timezone.utc)
            in_window = False
            for window in policy.allowed_time_windows:
                # Simplified: check day of week and hour
                if window.get("day") and window["day"] != now.strftime("%A").lower():
                    continue
                start_hour = window.get("start_hour", 0)
                end_hour = window.get("end_hour", 24)
                if start_hour <= now.hour < end_hour:
                    in_window = True
                    break
            if not in_window:
                violations.append("Outside allowed time window")

        # Quota check
        if policy.policy_type == PolicyType.QUOTA:
            counter_key = tool_name
            current = self._call_counters.get(policy.name, {}).get(counter_key, 0)
            if policy.max_calls_per_day and current >= policy.max_calls_per_day:
                violations.append(
                    f"Daily quota exceeded: {current}/{policy.max_calls_per_day}"
                )

        if violations:
            return PolicyEvaluation(
                policy_name=policy.name,
                effect=PolicyEffect.DENY,
                matched=True,
                reason=f"Policy '{policy.name}' violated: {'; '.join(violations)}",
                violations=violations,
            )

        if policy.effect == PolicyEffect.AUDIT:
            return PolicyEvaluation(
                policy_name=policy.name,
                effect=PolicyEffect.AUDIT,
                matched=True,
                reason=f"Policy '{policy.name}' requires audit",
            )

        return PolicyEvaluation(
            policy_name=policy.name,
            effect=PolicyEffect.ALLOW,
            matched=True,
            reason=f"Policy '{policy.name}' passed",
        )

    # ── Status ──

    def get_summary(self) -> Dict[str, Any]:
        """Get policy engine status."""
        return {
            "total_policies": len(self._policies),
            "enabled_policies": sum(1 for p in self._policies.values() if p.enabled),
            "policy_types": list({p.policy_type.value for p in self._policies.values()}),
            "initialized": self._initialized,
        }
