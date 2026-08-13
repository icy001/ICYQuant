"""
Policy Evaluator — evaluates policy rules against decision context.

To evaluate versioned policies with full traceability, use PolicyEngine.evaluate_versioned()
which leverages PolicyRegistry for active version resolution.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from .policy import InstitutionalPolicy as Policy
from .policy_rule import PolicyRule, RuleSeverity
from .policy_condition import PolicyCondition, ConditionLogic
from .decision_context import DecisionContext
from .decision_request import DecisionRequest


class PolicyEvaluator:
    """
    Evaluates individual policy rules against a decision context.
    Supports both simple threshold rules and composite condition rules.
    """

    # Known operators
    _OPERATORS = {
        "==": lambda a, b: a == b,
        "!=": lambda a, b: a != b,
        ">": lambda a, b: float(a) > float(b),
        ">=": lambda a, b: float(a) >= float(b),
        "<": lambda a, b: float(a) < float(b),
        "<=": lambda a, b: float(a) <= float(b),
    }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def evaluate_policy(
        self, policy: Policy, request: DecisionRequest, context: DecisionContext
    ) -> List[Dict[str, Any]]:
        """Evaluate all rules in a policy and return results."""
        results: List[Dict[str, Any]] = []
        for rule in policy.rules:
            if not rule.enabled:
                continue
            result = self._evaluate_rule(rule, request, context)
            results.append(result)
        return results

    def evaluate_rule(
        self, rule: PolicyRule, request: DecisionRequest, context: DecisionContext
    ) -> Dict[str, Any]:
        """Evaluate a single rule."""
        return self._evaluate_rule(rule, request, context)

    def evaluate_version(
        self,
        version: Any,  # PolicyVersion (lazy to avoid circular imports)
        request: DecisionRequest,
        context: DecisionContext,
    ) -> List[Dict[str, Any]]:
        """
        Evaluate all rules in a PolicyVersion.

        Returns a list of per-rule evaluation results with timing.
        """
        results: List[Dict[str, Any]] = []
        for rule in version.rules:
            if not rule.enabled:
                continue
            t0 = time.time()
            eval_result = self._evaluate_rule(rule, request, context)
            eval_result["evaluation_time_ms"] = (time.time() - t0) * 1000
            eval_result["version_id"] = version.version_id
            results.append(eval_result)
        return results

    def evaluate_rule_set(
        self,
        rule_set: Any,  # PolicyRuleSet
        request: DecisionRequest,
        context: DecisionContext,
    ) -> Dict[str, Any]:
        """
        Evaluate a PolicyRuleSet against a decision context.

        Returns an aggregated RuleSetResult.
        """
        from .policy_rule_set import RuleEvaluation, RuleSetResult, RuleSetEvaluationMode

        evaluations: List[RuleEvaluation] = []
        t_start = time.time()

        for rule in rule_set.active_rules:
            t0 = time.time()
            eval_result = self._evaluate_rule(rule, request, context)
            passed = eval_result.get("passed", True)
            evaluations.append(RuleEvaluation(
                rule_id=rule.rule_id,
                rule_name=rule.description or rule.rule_id,
                passed=passed,
                severity=rule.severity,
                metric=rule.metric,
                actual=eval_result.get("actual"),
                expected=str(rule.threshold),
                description=eval_result.get("description", ""),
                evaluation_time_ms=(time.time() - t0) * 1000,
            ))

            # Stop on first fail for FIRST_FAIL mode
            if (rule_set.evaluation_mode == RuleSetEvaluationMode.FIRST_FAIL
                    and not passed):
                break

        passed_count = sum(1 for e in evaluations if e.passed)
        failed_count = sum(1 for e in evaluations if not e.passed)
        all_passed = (
            passed_count == len(evaluations)
            if rule_set.evaluation_mode != RuleSetEvaluationMode.ANY
            else passed_count > 0
        )

        from .policy_rule import RuleSeverity as RS
        highest = RS.INFO
        for e in evaluations:
            if not e.passed and e.severity.value > highest.value:
                highest = e.severity

        return RuleSetResult(
            rule_set_id=rule_set.rule_set_id,
            rule_set_name=rule_set.name,
            passed=all_passed,
            rule_count=len(evaluations),
            passed_count=passed_count,
            failed_count=failed_count,
            highest_severity=highest,
            evaluations=evaluations,
            total_time_ms=(time.time() - t_start) * 1000,
        ).to_dict()

    # ------------------------------------------------------------------
    # Internal evaluation
    # ------------------------------------------------------------------

    def _evaluate_rule(
        self, rule: PolicyRule, request: DecisionRequest, context: DecisionContext
    ) -> Dict[str, Any]:
        # Resolve the actual value from context
        actual = self._resolve_metric(rule.metric, context, request)
        if actual is None:
            return {
                "rule_id": rule.rule_id,
                "metric": rule.metric,
                "passed": True,
                "severity": rule.severity.name,
                "actual": None,
                "expected": str(rule.threshold),
                "description": f"Metric '{rule.metric}' not found in context — skipped",
            }

        # Evaluate composite conditions first if present
        if rule.conditions:
            conditions_pass = self._evaluate_conditions(rule.conditions, rule.condition_logic, context)
            if not conditions_pass:
                return {
                    "rule_id": rule.rule_id,
                    "metric": rule.metric,
                    "passed": True,  # conditions not met means rule doesn't apply
                    "severity": rule.severity.name,
                    "actual": actual,
                    "expected": "conditions not met",
                    "description": rule.description,
                }

        # Get threshold (static or dynamic)
        threshold = rule.threshold
        if rule.threshold_key:
            threshold = self._resolve_metric(rule.threshold_key, context, request)
            if threshold is None:
                threshold = rule.threshold

        if threshold is None:
            return {
                "rule_id": rule.rule_id,
                "metric": rule.metric,
                "passed": True,
                "severity": rule.severity.name,
                "actual": actual,
                "expected": "no threshold",
                "description": "No threshold configured",
            }

        # Evaluate operator
        operator_fn = self._OPERATORS.get(rule.operator)
        if operator_fn is None:
            return {
                "rule_id": rule.rule_id,
                "metric": rule.metric,
                "passed": True,
                "severity": rule.severity.name,
                "actual": actual,
                "expected": str(threshold),
                "description": f"Unknown operator: {rule.operator}",
            }

        try:
            passed = operator_fn(actual, threshold)
        except (TypeError, ValueError):
            passed = True  # Can't compare → assume pass

        return {
            "rule_id": rule.rule_id,
            "metric": rule.metric,
            "passed": passed,
            "severity": rule.severity.name,
            "actual": actual,
            "expected": f"{rule.operator} {threshold}",
            "description": rule.description if not passed else "",
        }

    def _evaluate_conditions(
        self, conditions: List[PolicyCondition], logic: ConditionLogic, context: DecisionContext
    ) -> bool:
        """Evaluate composite conditions."""
        if not conditions:
            return True

        results = []
        for cond in conditions:
            value = self._resolve_metric(cond.metric, context, None)
            results.append(cond.evaluate(value))

        if logic == ConditionLogic.AND:
            return all(results)
        elif logic == ConditionLogic.OR:
            return any(results)
        elif logic == ConditionLogic.NOT:
            return not all(results)
        return True

    # ------------------------------------------------------------------
    # Metric resolution
    # ------------------------------------------------------------------

    def _resolve_metric(
        self, metric: str, context: DecisionContext, request: Optional[DecisionRequest]
    ) -> Any:
        """Resolve a metric name to its value from context or request."""
        # Try context fields
        if hasattr(context, metric):
            return getattr(context, metric)

        # Try context dict access
        ctx_dict = context.to_dict()
        if metric in ctx_dict:
            return ctx_dict[metric]

        # Try nested access (e.g., factor_exposures.AI)
        if "." in metric:
            parts = metric.split(".")
            value = ctx_dict.get(parts[0])
            for part in parts[1:]:
                if isinstance(value, dict):
                    value = value.get(part)
                else:
                    return None
            return value

        # Try request
        if request:
            if hasattr(request, metric):
                return getattr(request, metric)
            req_dict = request.to_dict()
            if metric in req_dict:
                return req_dict[metric]

        return None
