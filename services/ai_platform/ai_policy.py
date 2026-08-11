"""AI Policy — Policy evaluation and enforcement for AI decisions.

AI policies define the boundaries within which AI can operate.
They govern what AI can propose, what requires approval, and
what is automatically rejected.

Policy types:
    - Permissions (what AI can access)
    - Risk limits (max position, exposure)
    - Confidence thresholds (min confidence for auto-approval)
    - Operational limits (rate limits, time windows)
    - Guardrails (hard constraints that cannot be violated)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from .ai_context import AIContext
from .ai_session import AISession

if TYPE_CHECKING:
    from .ai_platform import AIPlatformConfig

logger = logging.getLogger(__name__)


class PolicyEffect(str, Enum):
    """Effect of a policy evaluation."""

    ALLOW = "allow"
    DENY = "deny"
    REQUIRE_APPROVAL = "require_approval"
    WARN = "warn"


class PolicyCategory(str, Enum):
    """Categories of AI policies."""

    PERMISSION = "permission"
    RISK = "risk"
    CONFIDENCE = "confidence"
    OPERATIONAL = "operational"
    GUARDRAIL = "guardrail"
    COMPLIANCE = "compliance"


@dataclass
class PolicyRule:
    """A single policy rule."""

    name: str
    category: PolicyCategory
    description: str
    effect: PolicyEffect = PolicyEffect.ALLOW
    condition: Optional[str] = None  # Python expression for evaluation
    threshold: float = 0.0
    enabled: bool = True
    priority: int = 0


@dataclass
class PolicyEvaluation:
    """Result of evaluating policies against a session."""

    evaluated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    rules_evaluated: int = 0
    rules_passed: int = 0
    rules_failed: List[Dict[str, Any]] = field(default_factory=list)
    overall_effect: PolicyEffect = PolicyEffect.ALLOW
    requires_approval: bool = False
    messages: List[str] = field(default_factory=list)


class AIPolicy:
    """AI Policy — governs AI operational boundaries.

    Policy hierarchy:
        1. Guardrails (hard constraints — cannot be violated)
        2. Risk limits (soft constraints — auto-reject if exceeded)
        3. Confidence thresholds (require approval below threshold)
        4. Operational limits (rate, size, scope)
        5. Default permissions

    AI operates within these policy boundaries at all times.
    """

    def __init__(self, config: "AIPlatformConfig") -> None:
        self.config = config
        self._rules: List[PolicyRule] = []
        self._init_default_rules()

    def _init_default_rules(self) -> None:
        """Initialize default policy rules."""
        self._rules = [
            # Guardrails — hard constraints
            PolicyRule(
                name="ai_no_direct_execution",
                category=PolicyCategory.GUARDRAIL,
                description="AI cannot directly execute orders",
                effect=PolicyEffect.DENY,
                priority=100,
            ),
            PolicyRule(
                name="risk_engine_required",
                category=PolicyCategory.GUARDRAIL,
                description="All AI decisions must pass through Risk Engine",
                effect=PolicyEffect.DENY,
                priority=100,
            ),
            # Risk limits
            PolicyRule(
                name="max_position_size",
                category=PolicyCategory.RISK,
                description="Maximum position size as fraction of portfolio",
                threshold=0.10,
                priority=50,
            ),
            PolicyRule(
                name="max_daily_turnover",
                category=PolicyCategory.RISK,
                description="Maximum daily portfolio turnover",
                threshold=0.30,
                priority=50,
            ),
            PolicyRule(
                name="max_sector_exposure",
                category=PolicyCategory.RISK,
                description="Maximum single sector exposure",
                threshold=0.25,
                priority=50,
            ),
            # Confidence thresholds
            PolicyRule(
                name="min_confidence_auto_approve",
                category=PolicyCategory.CONFIDENCE,
                description="Minimum confidence for auto-approval",
                effect=PolicyEffect.REQUIRE_APPROVAL,
                threshold=0.70,
                priority=40,
            ),
            PolicyRule(
                name="min_confidence_signal",
                category=PolicyCategory.CONFIDENCE,
                description="Minimum confidence to generate a signal",
                threshold=0.50,
                priority=40,
            ),
            # Operational limits
            PolicyRule(
                name="max_daily_signals",
                category=PolicyCategory.OPERATIONAL,
                description="Maximum AI signals per trading day",
                threshold=50,
                priority=30,
            ),
            PolicyRule(
                name="max_concurrent_positions",
                category=PolicyCategory.OPERATIONAL,
                description="Maximum concurrent positions",
                threshold=20,
                priority=30,
            ),
        ]

    # ------------------------------------------------------------------
    # Rule Management
    # ------------------------------------------------------------------

    def add_rule(self, rule: PolicyRule) -> None:
        """Add a new policy rule."""
        self._rules.append(rule)
        self._rules.sort(key=lambda r: r.priority, reverse=True)

    def remove_rule(self, name: str) -> bool:
        """Remove a policy rule by name."""
        before = len(self._rules)
        self._rules = [r for r in self._rules if r.name != name]
        return len(self._rules) < before

    def get_rule(self, name: str) -> Optional[PolicyRule]:
        """Get a rule by name."""
        for rule in self._rules:
            if rule.name == name:
                return rule
        return None

    def list_rules(self, category: Optional[PolicyCategory] = None) -> List[PolicyRule]:
        """List all rules, optionally filtered by category."""
        if category:
            return [r for r in self._rules if r.category == category]
        return list(self._rules)

    # ------------------------------------------------------------------
    # Policy Evaluation
    # ------------------------------------------------------------------

    async def evaluate(
        self,
        session: AISession,
        context: AIContext,
    ) -> PolicyEvaluation:
        """Evaluate all applicable policies against a session.

        Args:
            session: The AI session being evaluated.
            context: The AI context with accumulated data.

        Returns:
            PolicyEvaluation with pass/fail results.
        """
        evaluation = PolicyEvaluation()

        for rule in self._rules:
            if not rule.enabled:
                continue

            evaluation.rules_evaluated += 1
            passed = await self._evaluate_rule(rule, session, context)

            if passed:
                evaluation.rules_passed += 1
            else:
                evaluation.rules_failed.append({
                    "rule": rule.name,
                    "category": rule.category.value,
                    "effect": rule.effect.value,
                    "description": rule.description,
                })

                if rule.effect == PolicyEffect.DENY:
                    evaluation.overall_effect = PolicyEffect.DENY
                    evaluation.messages.append(
                        f"DENIED by {rule.name}: {rule.description}"
                    )
                    break
                elif rule.effect == PolicyEffect.REQUIRE_APPROVAL:
                    evaluation.requires_approval = True
                    evaluation.messages.append(
                        f"APPROVAL REQUIRED by {rule.name}: {rule.description}"
                    )
                elif rule.effect == PolicyEffect.WARN:
                    evaluation.messages.append(
                        f"WARNING from {rule.name}: {rule.description}"
                    )
                    logger.warning("Policy warning: %s — %s", rule.name, rule.description)

            if evaluation.overall_effect == PolicyEffect.DENY:
                break

        if evaluation.rules_failed and evaluation.overall_effect != PolicyEffect.DENY:
            evaluation.overall_effect = PolicyEffect.REQUIRE_APPROVAL

        logger.info(
            "Policy evaluation: %d/%d passed, effect=%s, approval=%s",
            evaluation.rules_passed,
            evaluation.rules_evaluated,
            evaluation.overall_effect.value,
            evaluation.requires_approval,
        )

        return evaluation

    async def _evaluate_rule(
        self,
        rule: PolicyRule,
        session: AISession,
        context: AIContext,
    ) -> bool:
        """Evaluate a single policy rule."""
        # Guardrail: AI cannot directly execute
        if rule.name == "ai_no_direct_execution":
            return session.mode is not None and str(session.mode) != "live"

        # Guardrail: Risk engine required
        if rule.name == "risk_engine_required":
            # In live mode, risk must be enabled
            if str(session.mode) == "live":
                return self.config.enable_risk
            return True

        # Risk limits are checked against context
        if rule.category == PolicyCategory.RISK:
            actual = context.get_data(rule.name, 0)
            if isinstance(actual, (int, float)):
                return actual <= rule.threshold
            return True  # No data to check against

        # Confidence thresholds
        if rule.category == PolicyCategory.CONFIDENCE:
            confidence = context.get_data("confidence", 0)
            signal = context.get_data("signal", {})
            if isinstance(signal, dict):
                confidence = signal.get("confidence", confidence)
            if isinstance(confidence, (int, float)):
                return confidence >= rule.threshold
            return True

        # Operational limits
        if rule.category == PolicyCategory.OPERATIONAL:
            # These would normally check against a counter service
            return True

        return True

    # ------------------------------------------------------------------
    # Quick Checks
    # ------------------------------------------------------------------

    async def check_permission(
        self,
        session: AISession,
        permission: str,
    ) -> bool:
        """Quick permission check."""
        rule = self.get_rule(permission)
        if rule and not rule.enabled:
            return False

        # Evaluate relevant rules
        for r in self._rules:
            if r.category == PolicyCategory.PERMISSION and r.name == permission:
                return r.effect != PolicyEffect.DENY

        return True
