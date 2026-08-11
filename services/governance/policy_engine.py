"""
Policy Engine — institutional policy evaluation and enforcement.

For versioned policy evaluation, see: policy_version.py, policy_registry.py
which provide full lifecycle management and version-aware evaluation.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional

from .policy import Policy
from .policy_rule import PolicyRule
from .policy_evaluator import PolicyEvaluator
from .decision_context import DecisionContext
from .decision_request import DecisionRequest


class PolicySeverity(Enum):
    """Severity level of policy breaches."""

    INFO = auto()
    WARNING = auto()
    REVIEW = auto()
    CRITICAL = auto()
    BLOCKING = auto()

    @classmethod
    def blocks_execution(cls, severity: "PolicySeverity") -> bool:
        return severity in (cls.CRITICAL, cls.BLOCKING)


@dataclass
class PolicyEvaluationResult:
    """Result of evaluating a set of policies."""

    passed: bool = True
    review_required: bool = False
    blocking: bool = False
    violations: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[Dict[str, Any]] = field(default_factory=list)
    info: List[Dict[str, Any]] = field(default_factory=list)
    evaluations: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def has_violations(self) -> bool:
        return len(self.violations) > 0

    @property
    def highest_severity(self) -> Optional[PolicySeverity]:
        if any(v.get("severity") == "BLOCKING" for v in self.violations):
            return PolicySeverity.BLOCKING
        if any(v.get("severity") == "CRITICAL" for v in self.violations):
            return PolicySeverity.CRITICAL
        if any(v.get("severity") == "REVIEW" for v in self.violations):
            return PolicySeverity.REVIEW
        if self.warnings:
            return PolicySeverity.WARNING
        if self.info:
            return PolicySeverity.INFO
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "review_required": self.review_required,
            "blocking": self.blocking,
            "violations": self.violations,
            "warnings": self.warnings,
            "info": self.info,
            "highest_severity": self.highest_severity.name if self.highest_severity else "NONE",
        }


class PolicyEngine:
    """
    Central policy evaluation engine.
    Manages a collection of policies and evaluates decisions against them.

    Also supports versioned policy evaluation via PolicyRegistry
    integration (see evaluate_versioned method).
    """

    def __init__(
        self,
        policies: Optional[List[Policy]] = None,
        registry: Any = None,  # PolicyRegistry (lazy import to avoid circular deps)
    ):
        self._policies: Dict[str, Policy] = {}
        self._evaluator = PolicyEvaluator()
        self._registry = registry  # Optional PolicyRegistry for versioned evaluation
        for p in (policies or []):
            self._policies[p.policy_id] = p

    # ------------------------------------------------------------------
    # Policy management
    # ------------------------------------------------------------------

    def register(self, policy: Policy) -> None:
        self._policies[policy.policy_id] = policy

    def remove(self, policy_id: str) -> None:
        self._policies.pop(policy_id, None)

    def get(self, policy_id: str) -> Optional[Policy]:
        return self._policies.get(policy_id)

    def list_policies(self) -> List[Policy]:
        return list(self._policies.values())

    def get_by_scope(self, scope: str) -> List[Policy]:
        return [p for p in self._policies.values() if p.scope == scope or p.scope == "GLOBAL"]

    # ------------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------------

    def evaluate(
        self, request: DecisionRequest, context: DecisionContext
    ) -> PolicyEvaluationResult:
        """Evaluate all applicable policies against a decision."""
        result = PolicyEvaluationResult()

        for policy in self._policies.values():
            if not self._policy_applies(policy, request):
                continue

            rule_results = self._evaluator.evaluate_policy(policy, request, context)
            for rule_result in rule_results:
                result.evaluations.append(rule_result)

                severity = PolicySeverity[rule_result.get("severity", "INFO")]
                entry = {
                    "policy_id": policy.policy_id,
                    "policy_name": policy.name,
                    "rule_id": rule_result.get("rule_id", ""),
                    "severity": severity.name,
                    "metric": rule_result.get("metric", ""),
                    "expected": rule_result.get("expected", ""),
                    "actual": rule_result.get("actual", ""),
                    "description": rule_result.get("description", ""),
                }

                if severity == PolicySeverity.BLOCKING:
                    result.passed = False
                    result.blocking = True
                    result.violations.append(entry)
                elif severity == PolicySeverity.CRITICAL:
                    result.passed = False
                    result.blocking = True
                    result.violations.append(entry)
                elif severity == PolicySeverity.REVIEW:
                    result.review_required = True
                    result.violations.append(entry)
                elif severity == PolicySeverity.WARNING:
                    result.warnings.append(entry)
                else:
                    result.info.append(entry)

        return result

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------

    def quick_check(self, request: DecisionRequest, context: DecisionContext) -> bool:
        """Simple pass/fail without detailed results."""
        result = self.evaluate(request, context)
        return result.passed and not result.blocking

    def get_active_policies(self) -> List[Policy]:
        return [p for p in self._policies.values() if p.enabled]

    # ------------------------------------------------------------------
    # Versioned evaluation (PolicyRegistry integration)
    # ------------------------------------------------------------------

    def set_registry(self, registry: Any) -> None:
        """Set the PolicyRegistry for versioned policy evaluation."""
        self._registry = registry

    @property
    def has_registry(self) -> bool:
        return self._registry is not None

    def evaluate_versioned(
        self, request: DecisionRequest, context: DecisionContext
    ) -> "VersionedPolicyResult":
        """
        Evaluate all active versioned policies against a decision.

        Uses PolicyRegistry to find and evaluate active policy versions.
        Returns a VersionedPolicyResult with full traceability.
        """
        from .policy_result import PolicyOutcome, VersionedPolicyResult

        result = VersionedPolicyResult(
            decision_id=f"DEC-{int(time.time() * 1_000_000)}",
            request_id=request.request_id,
        )

        if not self._registry:
            result.overall_verdict = "ALLOW"
            result.execution_allowed = True
            return result

        # Get applicable active versions sorted by priority
        active_versions = self._registry.list_for_evaluation(request.scope)
        result.active_versions = [
            {"policy_id": v.policy_id, "version_id": v.version_id,
             "version": v.version, "priority": v.priority.name}
            for v in active_versions
        ]

        t_start = time.time()

        for version in active_versions:
            t_eval_start = time.time()

            # Evaluate rules
            rule_results = []
            for rule in version.rules:
                if not rule.enabled:
                    continue
                eval_result = self._evaluator._evaluate_rule(rule, request, context)
                rule_results.append(eval_result)

            # Determine outcome
            failed_rules = [r for r in rule_results if not r.get("passed", True)]
            total_rules = len(rule_results)
            passed_rules = total_rules - len(failed_rules)

            if failed_rules:
                # Check if any failed rules are blocking
                from .policy_rule import RuleSeverity
                blocking_failures = [
                    r for r in failed_rules
                    if RuleSeverity[r.get("severity", "INFO")] in (
                        RuleSeverity.CRITICAL, RuleSeverity.BLOCKING
                    )
                ]
                if blocking_failures:
                    outcome = PolicyOutcome.blocked_result(
                        policy_id=version.policy_id,
                        version_id=version.version_id,
                        version=version.version,
                        policy_name=version.name,
                        reason=f"{len(blocking_failures)} blocking rule(s) failed",
                        total_rules=total_rules,
                        passed_rules=passed_rules,
                        failed_rules=len(failed_rules),
                        priority=version.priority,
                        evaluation_time_ms=(time.time() - t_eval_start) * 1000,
                    )
                else:
                    outcome = PolicyOutcome.review_result(
                        policy_id=version.policy_id,
                        version_id=version.version_id,
                        policy_name=version.name,
                        total_rules=total_rules,
                        passed_rules=passed_rules,
                        failed_rules=len(failed_rules),
                        priority=version.priority,
                        evaluation_time_ms=(time.time() - t_eval_start) * 1000,
                    )
            else:
                outcome = PolicyOutcome.passed_result(
                    policy_id=version.policy_id,
                    version_id=version.version_id,
                    version=version.version,
                    policy_name=version.name,
                    total_rules=total_rules,
                    passed_rules=passed_rules,
                    priority=version.priority,
                    evaluation_time_ms=(time.time() - t_eval_start) * 1000,
                )

            result.add_outcome(outcome)

        result.total_evaluation_time_ms = (time.time() - t_start) * 1000
        return result

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _policy_applies(policy: Policy, request: DecisionRequest) -> bool:
        if not policy.enabled:
            return False
        if policy.scope == "GLOBAL":
            return True
        # Check scope match
        if policy.scope == request.scope:
            return True
        # Check decision type match
        if policy.applies_to_decision_type(request.decision_type.name):
            return True
        return False

    def build_default_safety_policies(self) -> List[Policy]:
        """Build a set of sensible default safety policies."""
        return [
            self._make_max_allocation_policy(),
            self._make_max_leverage_policy(),
            self._make_min_liquidity_policy(),
            self._make_min_survival_policy(),
            self._make_risk_budget_policy(),
        ]

    @staticmethod
    def _make_max_allocation_policy() -> Policy:
        return Policy(
            policy_id="default-max-allocation",
            name="Maximum Single Strategy Allocation",
            description="No single strategy may exceed 25% of capital.",
            scope="STRATEGY",
            rules=[
                PolicyRule(
                    rule_id="max-alloc-25",
                    metric="strategy_weight",
                    operator="<=",
                    threshold=0.25,
                    severity=PolicySeverity.BLOCKING,
                    description="Strategy weight exceeds 25% limit",
                )
            ],
        )

    @staticmethod
    def _make_max_leverage_policy() -> Policy:
        return Policy(
            policy_id="default-max-leverage",
            name="Maximum Leverage",
            description="Total portfolio leverage must not exceed 3x.",
            scope="GLOBAL",
            rules=[
                PolicyRule(
                    rule_id="max-lev-3x",
                    metric="current_leverage",
                    operator="<=",
                    threshold=3.0,
                    severity=PolicySeverity.BLOCKING,
                    description="Leverage exceeds 3x limit",
                )
            ],
        )

    @staticmethod
    def _make_min_liquidity_policy() -> Policy:
        return Policy(
            policy_id="default-min-liquidity",
            name="Minimum Liquidity Requirement",
            description="Liquidity score must be >= 60 for new capital allocation.",
            scope="CAPITAL",
            rules=[
                PolicyRule(
                    rule_id="min-liq-60",
                    metric="liquidity_score",
                    operator=">=",
                    threshold=60.0,
                    severity=PolicySeverity.REVIEW,
                    description="Liquidity score below 60",
                )
            ],
        )

    @staticmethod
    def _make_min_survival_policy() -> Policy:
        return Policy(
            policy_id="default-min-survival",
            name="Minimum Survival Score",
            description="Capital survival score must be >= 70 for new allocations.",
            scope="CAPITAL",
            rules=[
                PolicyRule(
                    rule_id="min-surv-70",
                    metric="survival_score",
                    operator=">=",
                    threshold=70.0,
                    severity=PolicySeverity.BLOCKING,
                    description="Survival score below 70",
                )
            ],
        )

    @staticmethod
    def _make_risk_budget_policy() -> Policy:
        return Policy(
            policy_id="default-risk-budget",
            name="Risk Budget Compliance",
            description="Total risk must not exceed allocated risk budget.",
            scope="GLOBAL",
            rules=[
                PolicyRule(
                    rule_id="risk-budget-check",
                    metric="risk_budget_used",
                    operator="<=",
                    threshold_key="risk_budget_total",
                    severity=PolicySeverity.BLOCKING,
                    description="Risk budget breached",
                )
            ],
        )
