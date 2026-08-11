"""
Policy Module — rule-based governance for autonomous risk and execution decisions.

The Policy module defines the rule framework within which the entire
Autonomous Risk & Execution Optimization Platform operates. It provides
a declarative, composable policy system where each rule encodes a single
constraint (risk limit, position limit, exposure check, etc.) and the
Policy engine evaluates an execution context against all active rules
to produce a binding decision.

Policy-Driven Approach
----------------------
Every risk and execution decision flows through the policy engine.
Rather than hard-coding checks scattered across the codebase, all
governance is expressed as first-class PolicyRule objects:

    - RISK_LIMIT rules enforce VaR / ES / drawdown ceilings.
    - POSITION_LIMIT rules cap absolute or per-strategy notionals.
    - EXPOSURE_LIMIT rules constrain sector / asset / factor bets.
    - LEVERAGE_LIMIT rules control margin usage and debt ratios.
    - CONCENTRATION_LIMIT rules prevent over-weighting single names.
    - LIQUIDITY_LIMIT rules ensure sufficient market depth.
    - DRAWDOWN_LIMIT rules halt trading on cumulative loss thresholds.
    - VOLATILITY_LIMIT rules suppress activity during vol spikes.
    - FACTOR_LIMIT rules bound style / macro factor exposures.
    - REGIME_LIMIT rules adjust behaviour to market regime (NORMAL,
      STRESS, CRISIS).
    - EXECUTION_LIMIT rules govern execution-specific constraints
      (participation rate, order size, slippage tolerance).
    - GOVERNANCE rules enforce regulatory / compliance / internal
      policy requirements.

Each rule has:
    - A severity (CRITICAL / HIGH / MEDIUM / LOW) that determines
      escalation priority.
    - A comparator (GT / LT / GTE / LTE / EQ / NE) and threshold
      against which the context value is compared.
    - An action (ALLOW / WARN / RESIZE / REJECT / HALT) that the
      system takes when the rule is triggered.
    - A priority integer that controls evaluation ordering within
      the same severity.

The engine evaluates rules in priority order and produces a
PolicyEvaluation containing per-rule decisions, an overall action
derived from the highest-severity trigger, and lists of blocked /
warned / passed rules.  This evaluation is the single source of
truth for whether a proposed trade, allocation, or execution plan
may proceed.

Usage
-----
    policy = Policy(policy_id="firm-wide", name="Firm-Wide Risk Policy")

    await policy.add_rule(PolicyRule(
        name="Max Drawdown",
        category=PolicyRuleCategory.DRAWDOWN_LIMIT,
        severity=Severity.CRITICAL,
        condition={"field": "drawdown"},
        action=PolicyAction.HALT,
        threshold=0.15,
        comparator=Comparator.GTE,
        priority=1,
    ))

    evaluation = await policy.evaluate({"drawdown": 0.18, ...})
    if evaluation.overall_action == PolicyAction.HALT:
        # ... prevent execution
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class PolicyRuleCategory(Enum):
    """Classification of policy rule domains."""

    RISK_LIMIT = "risk_limit"
    POSITION_LIMIT = "position_limit"
    EXPOSURE_LIMIT = "exposure_limit"
    LEVERAGE_LIMIT = "leverage_limit"
    CONCENTRATION_LIMIT = "concentration_limit"
    LIQUIDITY_LIMIT = "liquidity_limit"
    DRAWDOWN_LIMIT = "drawdown_limit"
    VOLATILITY_LIMIT = "volatility_limit"
    FACTOR_LIMIT = "factor_limit"
    REGIME_LIMIT = "regime_limit"
    EXECUTION_LIMIT = "execution_limit"
    GOVERNANCE = "governance"


class Severity(Enum):
    """Severity levels for policy rules."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

    @property
    def weight(self) -> int:
        """Numeric weight for comparison (higher = more severe)."""
        return {
            "critical": 4,
            "high": 3,
            "medium": 2,
            "low": 1,
        }[self.value]


class PolicyAction(Enum):
    """Actions the policy engine can take."""

    ALLOW = "allow"
    WARN = "warn"
    RESIZE = "resize"
    REJECT = "reject"
    HALT = "halt"

    @property
    def weight(self) -> int:
        """Numeric weight for comparison (higher = more restrictive)."""
        return {
            "allow": 0,
            "warn": 1,
            "resize": 2,
            "reject": 3,
            "halt": 4,
        }[self.value]


class Comparator(Enum):
    """Comparison operators for rule threshold evaluation."""

    GT = "gt"
    LT = "lt"
    GTE = "gte"
    LTE = "lte"
    EQ = "eq"
    NE = "ne"

    def evaluate(self, value: float, threshold: float) -> bool:
        """
        Compare *value* against *threshold*.

        Returns True when the condition holds (rule triggers).
        """
        if self is Comparator.GT:
            return value > threshold
        if self is Comparator.LT:
            return value < threshold
        if self is Comparator.GTE:
            return value >= threshold
        if self is Comparator.LTE:
            return value <= threshold
        if self is Comparator.EQ:
            return value == threshold
        if self is Comparator.NE:
            return value != threshold
        return False


@dataclass
class PolicyRule:
    """
    A single policy rule.

    Each rule encodes one declarative constraint that the policy
    engine evaluates against an execution context dictionary.

    Attributes:
        id: Unique rule identifier (auto-generated).
        name: Human-readable rule name.
        description: Detailed explanation of the rule's purpose.
        category: Domain classification (risk, position, exposure, …).
        severity: Severity level — determines escalation priority.
        condition: Dictionary describing which context field to
            inspect.  Expected shape: ``{"field": "<key>"}``.
        action: Action to take when the rule triggers.
        threshold: Numeric threshold for the comparison.
        comparator: Comparison operator applied to the context value
            and the threshold.
        enabled: Whether the rule is currently active.
        priority: Evaluation ordering within the same severity
            (lower = evaluated first).
        metadata: Arbitrary key-value metadata (tags, notes, etc.).
    """

    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    description: str = ""
    category: PolicyRuleCategory = PolicyRuleCategory.GOVERNANCE
    severity: Severity = Severity.MEDIUM
    condition: dict[str, Any] = field(default_factory=dict)
    action: PolicyAction = PolicyAction.WARN
    threshold: float = 0.0
    comparator: Comparator = Comparator.GTE
    enabled: bool = True
    priority: int = 100
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class PolicyRuleDecision:
    """
    Per-rule evaluation result within a PolicyEvaluation.

    Records whether an individual rule triggered and, if so,
    what action it recommended.

    Attributes:
        rule_id: ID of the originating rule.
        rule_name: Name of the originating rule.
        triggered: Whether the rule's condition was satisfied.
        action: Action recommended by the rule (its configured
            action if triggered, ALLOW otherwise).
        severity: Severity of the originating rule.
        category: Category of the originating rule.
        value: Context value that was compared against the threshold.
        threshold: The rule's threshold at evaluation time.
        comparator: The rule's comparator at evaluation time.
        message: Human-readable explanation of the decision.
    """

    rule_id: str = ""
    rule_name: str = ""
    triggered: bool = False
    action: PolicyAction = PolicyAction.ALLOW
    severity: Severity = Severity.LOW
    category: PolicyRuleCategory = PolicyRuleCategory.GOVERNANCE
    value: float = 0.0
    threshold: float = 0.0
    comparator: Comparator = Comparator.GTE
    message: str = ""


@dataclass
class PolicyEvaluation:
    """
    Complete result of evaluating a context against a policy.

    The overall action is derived from the most severe triggered
    rule (CRITICAL > HIGH > MEDIUM > LOW), with ties broken by
    action restrictiveness (HALT > REJECT > RESIZE > WARN > ALLOW).

    Attributes:
        id: Unique evaluation identifier.
        policy_id: ID of the policy that produced this evaluation.
        timestamp: When the evaluation was performed.
        context: The execution context dictionary that was evaluated.
        decisions: Per-rule decisions for every rule that was
            evaluated (active rules only).
        overall_action: The binding action the system should take.
        blocked_rules: List of rule decisions that resulted in
            REJECT or HALT actions.
        warnings: List of rule decisions that resulted in WARN
            actions.
        passed_rules: List of rule decisions that resulted in ALLOW
            or RESIZE actions.
        duration_ms: Wall-clock evaluation time in milliseconds.
    """

    id: str = field(default_factory=lambda: str(uuid4()))
    policy_id: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    context: dict[str, Any] = field(default_factory=dict)
    decisions: list[PolicyRuleDecision] = field(default_factory=list)
    overall_action: PolicyAction = PolicyAction.ALLOW
    blocked_rules: list[PolicyRuleDecision] = field(default_factory=list)
    warnings: list[PolicyRuleDecision] = field(default_factory=list)
    passed_rules: list[PolicyRuleDecision] = field(default_factory=list)
    duration_ms: float = 0.0


@dataclass
class PolicyStats:
    """
    Aggregate statistics for a policy.

    Provides observability into rule usage, evaluation throughput,
    and trigger frequency across categories and severities.

    Attributes:
        total_rules: Total number of rules (enabled + disabled).
        active_rules: Number of currently enabled rules.
        by_category: Rule counts grouped by PolicyRuleCategory.
        by_severity: Rule counts grouped by Severity.
        evaluations_total: Lifetime total evaluations performed.
        blocked_total: Lifetime total evaluations that resulted in
            at least one blocked (REJECT / HALT) rule.
        warned_total: Lifetime total evaluations that resulted in
            at least one warned rule.
        avg_evaluation_ms: Rolling average evaluation duration.
    """

    total_rules: int = 0
    active_rules: int = 0
    by_category: dict[str, int] = field(default_factory=dict)
    by_severity: dict[str, int] = field(default_factory=dict)
    evaluations_total: int = 0
    blocked_total: int = 0
    warned_total: int = 0
    avg_evaluation_ms: float = 0.0


class Policy:
    """
    Rule-based policy engine for autonomous risk and execution.

    A Policy owns an ordered collection of :class:`PolicyRule`
    objects and evaluates execution contexts against them to
    produce binding :class:`PolicyEvaluation` decisions.

    Rules are evaluated in ascending priority order (lower number
    first).  The overall action for an evaluation is the most
    restrictive action among all triggered rules, with severity
    acting as a tiebreaker.

    Thread Safety
    -------------
    This class is **not** thread-safe.  Use from a single
    asyncio event loop or protect with an external lock if
    concurrent access is required.

    Usage::

        policy = Policy(policy_id="global", name="Global Policy")

        await policy.add_rule(PolicyRule(
            name="VaR Limit",
            category=PolicyRuleCategory.RISK_LIMIT,
            severity=Severity.CRITICAL,
            condition={"field": "var_ratio"},
            action=PolicyAction.HALT,
            threshold=1.0,
            comparator=Comparator.GTE,
        ))

        result = await policy.evaluate({"var_ratio": 1.15})
        if result.overall_action == PolicyAction.HALT:
            # block the trade
    """

    def __init__(self, policy_id: str = "", name: str = "") -> None:
        self._policy_id: str = policy_id or str(uuid4())
        self._name: str = name or "Unnamed Policy"
        self._rules: dict[str, PolicyRule] = {}
        self._evaluations_total: int = 0
        self._blocked_total: int = 0
        self._warned_total: int = 0
        self._evaluation_durations: list[float] = []

    # ── Rule Management ──────────────────────────────────────

    async def add_rule(self, rule: PolicyRule) -> str:
        """
        Register a new rule with the policy.

        If a rule with the same ID already exists it is replaced.

        Args:
            rule: The PolicyRule to add.

        Returns:
            The ID of the added rule.
        """
        self._rules[rule.id] = rule
        logger.info(
            "Rule added: id=%s name=%s category=%s severity=%s",
            rule.id, rule.name, rule.category.value, rule.severity.value,
        )
        return rule.id

    async def remove_rule(self, rule_id: str) -> bool:
        """
        Remove a rule by its ID.

        Args:
            rule_id: The ID of the rule to remove.

        Returns:
            True if the rule was found and removed, False otherwise.
        """
        if rule_id in self._rules:
            removed = self._rules.pop(rule_id)
            logger.info("Rule removed: id=%s name=%s", removed.id, removed.name)
            return True
        logger.warning("Rule not found for removal: id=%s", rule_id)
        return False

    async def get_rule(self, rule_id: str) -> Optional[PolicyRule]:
        """
        Retrieve a rule by its ID.

        Args:
            rule_id: The ID of the rule to retrieve.

        Returns:
            The matching PolicyRule, or None if not found.
        """
        return self._rules.get(rule_id)

    async def get_active_rules(self) -> list[PolicyRule]:
        """
        Return all currently enabled rules sorted by priority.

        Returns:
            List of active PolicyRule objects ordered by ascending
            priority (lowest number = evaluated first).
        """
        active = [r for r in self._rules.values() if r.enabled]
        active.sort(key=lambda r: r.priority)
        return active

    async def enable_rule(self, rule_id: str) -> bool:
        """
        Enable a rule by its ID.

        Args:
            rule_id: The ID of the rule to enable.

        Returns:
            True if the rule was found and enabled, False otherwise.
        """
        rule = self._rules.get(rule_id)
        if rule is None:
            logger.warning("Rule not found for enable: id=%s", rule_id)
            return False
        rule.enabled = True
        logger.info("Rule enabled: id=%s name=%s", rule.id, rule.name)
        return True

    async def disable_rule(self, rule_id: str) -> bool:
        """
        Disable a rule by its ID.

        Args:
            rule_id: The ID of the rule to disable.

        Returns:
            True if the rule was found and disabled, False otherwise.
        """
        rule = self._rules.get(rule_id)
        if rule is None:
            logger.warning("Rule not found for disable: id=%s", rule_id)
            return False
        rule.enabled = False
        logger.info("Rule disabled: id=%s name=%s", rule.id, rule.name)
        return True

    # ── Policy Evaluation ────────────────────────────────────

    async def evaluate(self, context: dict[str, Any]) -> PolicyEvaluation:
        """
        Evaluate an execution context against all active rules.

        Rules are evaluated in ascending priority order.  For each
        rule the engine extracts the context field specified in the
        rule's ``condition["field"]``, applies the rule's comparator
        against its threshold, and records a decision.

        The overall action is determined by the most severe triggered
        rule, with ties broken by action restrictiveness:

            CRITICAL + HALT  →  HALT
            CRITICAL + REJECT →  REJECT
            HIGH + REJECT    →  REJECT
            HIGH + RESIZE    →  RESIZE
            MEDIUM + WARN    →  WARN
            (no triggers)    →  ALLOW

        Args:
            context: Dictionary containing the execution / risk
                metrics to evaluate (e.g., ``{"drawdown": 0.05,
                "var_ratio": 0.8, "participation_rate": 0.12}``).

        Returns:
            A :class:`PolicyEvaluation` containing per-rule
            decisions, the overall action, and categorised lists
            of blocked / warned / passed rules.
        """
        start = time.perf_counter()

        active_rules = await self.get_active_rules()
        decisions: list[PolicyRuleDecision] = []
        blocked: list[PolicyRuleDecision] = []
        warned: list[PolicyRuleDecision] = []
        passed: list[PolicyRuleDecision] = []

        # Track the most severe triggered action for overall_action
        top_severity_weight = -1
        top_action_weight = -1
        top_action = PolicyAction.ALLOW

        for rule in active_rules:
            field_name = rule.condition.get("field", "")
            if not field_name or field_name not in context:
                # Field missing from context — skip rule silently
                decision = PolicyRuleDecision(
                    rule_id=rule.id,
                    rule_name=rule.name,
                    triggered=False,
                    action=PolicyAction.ALLOW,
                    severity=rule.severity,
                    category=rule.category,
                    value=0.0,
                    threshold=rule.threshold,
                    comparator=rule.comparator,
                    message=f"Field '{field_name}' not found in context",
                )
                decisions.append(decision)
                passed.append(decision)
                continue

            value = float(context[field_name])
            triggered = rule.comparator.evaluate(value, rule.threshold)

            if triggered:
                decision = PolicyRuleDecision(
                    rule_id=rule.id,
                    rule_name=rule.name,
                    triggered=True,
                    action=rule.action,
                    severity=rule.severity,
                    category=rule.category,
                    value=value,
                    threshold=rule.threshold,
                    comparator=rule.comparator,
                    message=(
                        f"Rule '{rule.name}' triggered: "
                        f"{value:.4f} {rule.comparator.value} {rule.threshold:.4f} "
                        f"→ {rule.action.value.upper()}"
                    ),
                )

                sev_w = rule.severity.weight
                act_w = rule.action.weight

                if sev_w > top_severity_weight:
                    top_severity_weight = sev_w
                    top_action_weight = act_w
                    top_action = rule.action
                elif sev_w == top_severity_weight and act_w > top_action_weight:
                    top_action_weight = act_w
                    top_action = rule.action

                if rule.action in (PolicyAction.REJECT, PolicyAction.HALT):
                    blocked.append(decision)
                elif rule.action == PolicyAction.WARN:
                    warned.append(decision)
                else:
                    passed.append(decision)
            else:
                decision = PolicyRuleDecision(
                    rule_id=rule.id,
                    rule_name=rule.name,
                    triggered=False,
                    action=PolicyAction.ALLOW,
                    severity=rule.severity,
                    category=rule.category,
                    value=value,
                    threshold=rule.threshold,
                    comparator=rule.comparator,
                    message=(
                        f"Rule '{rule.name}' passed: "
                        f"{value:.4f} not {rule.comparator.value} {rule.threshold:.4f}"
                    ),
                )
                passed.append(decision)

            decisions.append(decision)

        elapsed_ms = (time.perf_counter() - start) * 1000.0

        evaluation = PolicyEvaluation(
            policy_id=self._policy_id,
            context=context,
            decisions=decisions,
            overall_action=top_action,
            blocked_rules=blocked,
            warnings=warned,
            passed_rules=passed,
            duration_ms=elapsed_ms,
        )

        # Update aggregate statistics
        self._evaluations_total += 1
        if blocked:
            self._blocked_total += 1
        if warned:
            self._warned_total += 1
        self._evaluation_durations.append(elapsed_ms)
        # Keep only the last 500 durations for rolling average
        if len(self._evaluation_durations) > 500:
            self._evaluation_durations = self._evaluation_durations[-500:]

        logger.info(
            "Policy evaluation: policy=%s action=%s blocked=%d warned=%d duration=%.3fms",
            self._name, top_action.value, len(blocked), len(warned), elapsed_ms,
        )

        return evaluation

    # ── Introspection ────────────────────────────────────────

    async def get_policy(self) -> dict[str, Any]:
        """
        Return a dictionary summary of the policy configuration.

        Includes the policy metadata and a condensed view of all
        rules (without per-rule evaluation state).

        Returns:
            Dictionary with keys: ``policy_id``, ``name``,
            ``total_rules``, ``active_rules``, ``rules``.
        """
        rules_summary = []
        for rule in self._rules.values():
            rules_summary.append({
                "id": rule.id,
                "name": rule.name,
                "category": rule.category.value,
                "severity": rule.severity.value,
                "action": rule.action.value,
                "comparator": rule.comparator.value,
                "threshold": rule.threshold,
                "enabled": rule.enabled,
                "priority": rule.priority,
            })
        return {
            "policy_id": self._policy_id,
            "name": self._name,
            "total_rules": len(self._rules),
            "active_rules": sum(1 for r in self._rules.values() if r.enabled),
            "rules": rules_summary,
        }

    async def get_stats(self) -> PolicyStats:
        """
        Return aggregate statistics for the policy.

        Provides counts of rules by category and severity,
        evaluation throughput, trigger rates, and average
        evaluation latency.

        Returns:
            A :class:`PolicyStats` instance populated with
            current metrics.
        """
        by_category: dict[str, int] = {}
        by_severity: dict[str, int] = {}

        for rule in self._rules.values():
            cat = rule.category.value
            by_category[cat] = by_category.get(cat, 0) + 1

            sev = rule.severity.value
            by_severity[sev] = by_severity.get(sev, 0) + 1

        avg_ms = 0.0
        if self._evaluation_durations:
            avg_ms = sum(self._evaluation_durations) / len(self._evaluation_durations)

        return PolicyStats(
            total_rules=len(self._rules),
            active_rules=sum(1 for r in self._rules.values() if r.enabled),
            by_category=by_category,
            by_severity=by_severity,
            evaluations_total=self._evaluations_total,
            blocked_total=self._blocked_total,
            warned_total=self._warned_total,
            avg_evaluation_ms=avg_ms,
        )

    # ── Properties ───────────────────────────────────────────

    @property
    def policy_id(self) -> str:
        """Unique policy identifier."""
        return self._policy_id

    @property
    def name(self) -> str:
        """Human-readable policy name."""
        return self._name

    @property
    def rules(self) -> dict[str, PolicyRule]:
        """Direct access to the rules dictionary (read-only view)."""
        return self._rules