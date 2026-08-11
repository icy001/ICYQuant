"""Policy Engine — centralized policy definition and enforcement for the AI platform.

The PolicyEngine defines and enforces policies across the AI platform.
Policies control what agents can do, which tools they can call, what data
they can access, and under what conditions operations are permitted.

Policy types:
    - Prompt Policy: content filtering, injection prevention
    - Tool Policy: which tools are allowed per agent/user
    - Data Policy: data access and PII handling
    - Compliance Policy: regulatory compliance rules
    - Risk Policy: risk-based operation limits
    - Rate Policy: rate limiting and throttling
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class PolicyType(str, Enum):
    """Types of enforceable policies."""
    PROMPT = "prompt"
    TOOL = "tool"
    DATA = "data"
    COMPLIANCE = "compliance"
    RISK = "risk"
    RATE = "rate"


class PolicyAction(str, Enum):
    """Actions taken when a policy is triggered."""
    ALLOW = "allow"
    BLOCK = "block"
    WARN = "warn"
    LOG = "log"
    REDACT = "redact"
    ESCALATE = "escalate"


@dataclass
class PolicyRule:
    """A single policy rule."""
    rule_id: str = ""
    policy_type: PolicyType = PolicyType.PROMPT
    name: str = ""
    description: str = ""
    action: PolicyAction = PolicyAction.BLOCK
    condition: Optional[Callable] = None
    priority: int = 0
    enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PolicyEvaluation:
    """Result of evaluating policies against a request."""
    allowed: bool = True
    blocked_by: Optional[str] = None
    warnings: List[str] = field(default_factory=list)
    rules_matched: List[str] = field(default_factory=list)
    actions_taken: Dict[str, PolicyAction] = field(default_factory=dict)
    evaluated_at: float = field(default_factory=time.monotonic)


class PolicyEngine:
    """Centralized policy definition and enforcement engine.

    Evaluates all applicable policies for every AI request, ensuring
    compliance with organizational, regulatory, and safety requirements.

    Usage:
        pe = PolicyEngine()
        await pe.initialize()
        pe.add_rule(PolicyRule(rule_id="block_pii", policy_type=PolicyType.DATA, action=PolicyAction.BLOCK))
        result = await pe.evaluate(request_context)
    """

    def __init__(self) -> None:
        self._rules: Dict[str, PolicyRule] = {}
        self._default_actions: Dict[PolicyType, PolicyAction] = {
            PolicyType.PROMPT: PolicyAction.BLOCK,
            PolicyType.TOOL: PolicyAction.BLOCK,
            PolicyType.DATA: PolicyAction.BLOCK,
            PolicyType.COMPLIANCE: PolicyAction.BLOCK,
            PolicyType.RISK: PolicyAction.WARN,
            PolicyType.RATE: PolicyAction.WARN,
        }
        self._evaluation_count: int = 0
        self._block_count: int = 0
        self._initialized: bool = False
        logger.info("PolicyEngine created")

    async def initialize(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        logger.info("PolicyEngine initialized")

    async def shutdown(self) -> None:
        self._rules.clear()
        self._initialized = False
        logger.info("PolicyEngine shutdown complete")

    def add_rule(self, rule: PolicyRule) -> None:
        """Add a policy rule."""
        self._rules[rule.rule_id] = rule
        logger.info("PolicyEngine: added rule %s (%s)", rule.rule_id, rule.policy_type.value)

    def remove_rule(self, rule_id: str) -> bool:
        """Remove a policy rule."""
        if rule_id in self._rules:
            del self._rules[rule_id]
            return True
        return False

    def enable_rule(self, rule_id: str) -> bool:
        """Enable a policy rule."""
        rule = self._rules.get(rule_id)
        if rule:
            rule.enabled = True
            return True
        return False

    def disable_rule(self, rule_id: str) -> bool:
        """Disable a policy rule."""
        rule = self._rules.get(rule_id)
        if rule:
            rule.enabled = False
            return True
        return False

    async def evaluate(self, context: Dict[str, Any]) -> PolicyEvaluation:
        """Evaluate all applicable policies against a request context.

        Context should include:
            - user_id: str
            - agent_type: str
            - request_type: str
            - tools_requested: List[str]
            - data_accessed: List[str]
            - risk_level: str
        """
        self._evaluation_count += 1
        result = PolicyEvaluation()

        enabled_rules = sorted(
            [r for r in self._rules.values() if r.enabled],
            key=lambda r: r.priority,
            reverse=True,
        )

        for rule in enabled_rules:
            # Check if rule applies to this context
            if rule.condition and not rule.condition(context):
                continue

            result.rules_matched.append(rule.rule_id)
            result.actions_taken[rule.rule_id] = rule.action

            if rule.action == PolicyAction.BLOCK:
                result.allowed = False
                result.blocked_by = rule.rule_id
                self._block_count += 1
                logger.warning("PolicyEngine: blocked by rule %s", rule.rule_id)
                break
            elif rule.action == PolicyAction.WARN:
                result.warnings.append(f"Rule {rule.rule_id}: {rule.description}")
            elif rule.action == PolicyAction.ESCALATE:
                result.warnings.append(f"ESCALATE: Rule {rule.rule_id} triggered")
                logger.warning("PolicyEngine: escalation triggered by rule %s", rule.rule_id)

        return result

    async def evaluate_prompt(self, prompt_text: str, user_id: str = "") -> PolicyEvaluation:
        """Evaluate policies specifically for a prompt."""
        return await self.evaluate({
            "user_id": user_id,
            "request_type": "prompt",
            "prompt_text": prompt_text,
        })

    async def evaluate_tool_call(self, tool_name: str, user_id: str = "", agent_type: str = "") -> PolicyEvaluation:
        """Evaluate policies for a tool call."""
        return await self.evaluate({
            "user_id": user_id,
            "agent_type": agent_type,
            "request_type": "tool_call",
            "tools_requested": [tool_name],
        })

    def get_rules_by_type(self, policy_type: PolicyType) -> List[PolicyRule]:
        """Get all rules of a specific type."""
        return [r for r in self._rules.values() if r.policy_type == policy_type]

    def get_summary(self) -> Dict[str, Any]:
        by_type: Dict[str, int] = {}
        for r in self._rules.values():
            by_type[r.policy_type.value] = by_type.get(r.policy_type.value, 0) + 1
        return {
            "initialized": self._initialized,
            "total_rules": len(self._rules),
            "enabled_rules": len([r for r in self._rules.values() if r.enabled]),
            "by_type": by_type,
            "evaluations": self._evaluation_count,
            "blocks": self._block_count,
        }
