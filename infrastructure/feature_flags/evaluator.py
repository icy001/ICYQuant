"""
Feature flag platform evaluation engine.

Provides the core evaluation logic for
determining feature flag values based on
flag type, rules, and context.

Integrates with the Targeting Rules Engine
for complex rule-based evaluation, the
Rollout Engine for percentage-based deployment,
the Canary Manager for staged deployments,
and the Experiment Manager for A/B testing.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

from .constants import EvaluationResult, EvaluationStrategy, FeatureFlagType
from .exceptions import FeatureFlagEvaluationError
from .models import (
    FeatureContext,
    FeatureEvaluationResult,
    FeatureFlag,
    FeatureRule,
)
from .rollout import RolloutEngine, RolloutPolicy
from .targeting.engine import TargetingEngine
from .targeting.rules import TargetRule
from .utils import is_in_rollout

logger = logging.getLogger(__name__)


class FeatureEvaluator:
    """
    Core evaluation engine for feature flags.

    Implements the logic to determine a flag's
    value based on its type, evaluation strategy,
    targeting rules, percentage rollout, and the
    provided context.

    Supports:
        - Boolean flags (simple on/off)
        - Rule-based targeting (attribute matching)
        - Percentage rollouts (consistent hashing)
        - Progressive deployment (multi-stage rollout)
        - Segment-based rollout (targeted groups)
        - Kill switch (global emergency toggle)
        - Canary release (staged deployment with health checks)
        - Experiment-based evaluation (A/B testing)

    Usage:
        evaluator = FeatureEvaluator()
        result = await evaluator.evaluate(flag, context)
    """

    def __init__(self) -> None:
        self._evaluation_count = 0
        self._error_count = 0
        self._total_duration_ms = 0.0
        self._rule_match_count = 0
        self._default_falls = 0
        self._lock = asyncio.Lock()
        self._targeting_engine = TargetingEngine()
        self._rollout_engine = RolloutEngine()
        self._use_targeting_engine = True
        self._use_rollout_engine = True
        # Canary & experiment integration (lazy-initialized)
        self._canary_manager = None
        self._experiment_manager = None

    async def evaluate(
        self,
        flag: FeatureFlag,
        context: Optional[FeatureContext] = None,
    ) -> FeatureEvaluationResult:
        """
        Evaluate a feature flag.

        Args:
            flag: Feature flag to evaluate.
            context: Evaluation context (user, account, etc).

        Returns:
            FeatureEvaluationResult with the flag value.

        Raises:
            FeatureFlagEvaluationError: On evaluation failure.
        """
        start = time.perf_counter()
        self._evaluation_count += 1

        try:
            # Kill switch check
            if flag.flag_type == FeatureFlagType.KILL_SWITCH:
                return self._evaluate_kill_switch(flag, start)

            # Disabled flag
            if not flag.enabled:
                disabled_value = (
                    False
                    if flag.flag_type == FeatureFlagType.BOOLEAN
                    else flag.default_value
                )
                return self._create_result(
                    flag=flag,
                    value=disabled_value,
                    result=EvaluationResult.MISS,
                    reason="flag_disabled",
                    matched_rule_id=None,
                    start=start,
                )

            # Status check
            if flag.status.value in ("inactive", "archived", "deprecated"):
                return self._create_result(
                    flag=flag,
                    value=flag.default_value,
                    result=EvaluationResult.MISS,
                    reason=f"flag_{flag.status.value}",
                    matched_rule_id=None,
                    start=start,
                )

            # Evaluate by strategy
            if flag.strategy == EvaluationStrategy.PERCENTAGE:
                return await self._evaluate_percentage(flag, context, start)
            elif flag.strategy == EvaluationStrategy.RULE_BASED:
                return await self._evaluate_rules(flag, context, start)
            elif flag.strategy == EvaluationStrategy.EXPERIMENT:
                return await self._evaluate_experiment(flag, context, start)
            elif flag.strategy == EvaluationStrategy.CANARY:
                return await self._evaluate_canary(flag, context, start)
            else:
                return self._evaluate_static(flag, start)

        except Exception as e:
            self._error_count += 1
            duration_ms = (time.perf_counter() - start) * 1000
            self._total_duration_ms += duration_ms

            logger.error(
                "Evaluation failed for flag %s: %s",
                flag.key, e,
            )

            return self._create_result(
                flag=flag,
                value=flag.default_value,
                result=EvaluationResult.ERROR,
                reason=str(e),
                matched_rule_id=None,
                start=start,
                error=True,
            )

    def _evaluate_static(
        self,
        flag: FeatureFlag,
        start: float,
    ) -> FeatureEvaluationResult:
        """Evaluate a static boolean flag."""
        return self._create_result(
            flag=flag,
            value=flag.default_value,
            result=EvaluationResult.HIT if flag.enabled else EvaluationResult.MISS,
            reason="static_eval",
            matched_rule_id=None,
            start=start,
        )

    def _evaluate_kill_switch(
        self,
        flag: FeatureFlag,
        start: float,
    ) -> FeatureEvaluationResult:
        """Evaluate a kill switch flag. Kill switch takes precedence."""
        # Kill switch: if flag is enabled, it means the kill switch is ON,
        # returning False to disable the feature
        if flag.enabled:
            return self._create_result(
                flag=flag,
                value=False,
                result=EvaluationResult.HIT,
                reason="kill_switch_active",
                matched_rule_id=None,
                start=start,
            )
        else:
            return self._create_result(
                flag=flag,
                value=flag.default_value,
                result=EvaluationResult.MISS,
                reason="kill_switch_inactive",
                matched_rule_id=None,
                start=start,
            )

    async def _evaluate_rules(
        self,
        flag: FeatureFlag,
        context: Optional[FeatureContext],
        start: float,
    ) -> FeatureEvaluationResult:
        """Evaluate rule-based targeting using TargetingEngine."""
        if not flag.rules:
            self._default_falls += 1
            return self._create_result(
                flag=flag,
                value=flag.default_value,
                result=EvaluationResult.NO_RULE,
                reason="no_rules_defined",
                matched_rule_id=None,
                start=start,
            )

        # Convert FeatureRule list to TargetRule list for targeting engine
        targeting_rules = self._convert_rules(flag.rules)

        # Use TargetingEngine for evaluation
        result = await self._targeting_engine.evaluate(
            rules=targeting_rules,
            feature_context=context,
            default_value=flag.default_value,
            use_cache=True,
        )

        if result.matched:
            self._rule_match_count += 1
            return self._create_result(
                flag=flag,
                value=result.value,
                result=EvaluationResult.HIT,
                reason=f"targeting_match:{result.rule_id}",
                matched_rule_id=result.rule_id,
                start=start,
            )
        else:
            self._default_falls += 1
            return self._create_result(
                flag=flag,
                value=flag.default_value,
                result=EvaluationResult.NO_RULE,
                reason="no_targeting_rule_matched",
                matched_rule_id=None,
                start=start,
            )

    def _convert_rules(self, rules: List[FeatureRule]) -> List[TargetRule]:
        """Convert FeatureRule objects to TargetRule objects."""
        return [
            TargetRule(
                rule_id=r.rule_id,
                priority=r.priority,
                expression=r.condition,
                value=r.value,
                enabled=r.enabled,
                description=r.description,
                tags=r.tags,
            )
            for r in rules
        ]

    async def _evaluate_percentage(
        self,
        flag: FeatureFlag,
        context: Optional[FeatureContext],
        start: float,
    ) -> FeatureEvaluationResult:
        """Evaluate percentage-based rollout using RolloutEngine."""
        if context is None or not context.target_id:
            self._default_falls += 1
            return self._create_result(
                flag=flag,
                value=flag.default_value,
                result=EvaluationResult.NO_RULE,
                reason="no_target_id",
                matched_rule_id=None,
                start=start,
            )

        # Use RolloutEngine when enabled
        if self._use_rollout_engine:
            policy = self._extract_rollout_policy(flag)
            if policy:
                assignment = await self._rollout_engine.evaluate(
                    flag_key=flag.key,
                    target_id=context.target_id,
                    attributes=context.attributes if context else {},
                    policy=policy,
                )
                if assignment.assigned:
                    self._rule_match_count += 1
                    value = self._resolve_rollout_value(flag, assignment.percentage)
                    return self._create_result(
                        flag=flag,
                        value=value,
                        result=EvaluationResult.HIT,
                        reason=f"rollout:{assignment.percentage}%:{assignment.version}",
                        matched_rule_id=None,
                        start=start,
                    )
                else:
                    self._default_falls += 1
                    return self._create_result(
                        flag=flag,
                        value=flag.default_value,
                        result=EvaluationResult.NO_RULE,
                        reason=f"rollout_not_assigned:{assignment.percentage}%",
                        matched_rule_id=None,
                        start=start,
                    )

        # Legacy path: find percentage rule
        for rule in flag.rules:
            if not rule.enabled:
                continue
            try:
                percentage = float(rule.condition)
                if is_in_rollout(
                    flag.key, context.target_id, percentage,
                ):
                    self._rule_match_count += 1
                    return self._create_result(
                        flag=flag,
                        value=rule.value,
                        result=EvaluationResult.HIT,
                        reason=f"percentage_rollout:{percentage}%",
                        matched_rule_id=rule.rule_id,
                        start=start,
                    )
            except (ValueError, TypeError):
                continue

        self._default_falls += 1
        return self._create_result(
            flag=flag,
            value=flag.default_value,
            result=EvaluationResult.NO_RULE,
            reason="percentage_not_matched",
            matched_rule_id=None,
            start=start,
        )

    def _extract_rollout_policy(self, flag: FeatureFlag) -> Optional[RolloutPolicy]:
        """Extract rollout policy from flag configuration."""
        # Check metadata for rollout config
        metadata = flag.metadata or {}
        percentage = metadata.get("rollout_percentage", metadata.get("percentage"))
        if percentage is not None:
            try:
                return RolloutPolicy(
                    percentage=float(percentage),
                    hash_key=metadata.get("rollout_hash_key", "account_id"),
                    algorithm=metadata.get("rollout_algorithm", "murmur3"),
                )
            except (ValueError, TypeError):
                pass

        # Check rules for percentage-based rules
        for rule in flag.rules:
            if not rule.enabled:
                continue
            try:
                pct = float(rule.condition)
                return RolloutPolicy(
                    percentage=pct,
                    hash_key="account_id",
                )
            except (ValueError, TypeError):
                continue

        return None

    def _resolve_rollout_value(
        self,
        flag: FeatureFlag,
        percentage: float,
    ) -> Any:
        """Resolve the value to return for a rollout assignment."""
        # Find matching rule for this percentage
        for rule in flag.rules:
            if not rule.enabled:
                continue
            try:
                if float(rule.condition) == percentage:
                    return rule.value
            except (ValueError, TypeError):
                continue

        return True

    async def _evaluate_experiment(
        self,
        flag: FeatureFlag,
        context: Optional[FeatureContext],
        start: float,
    ) -> FeatureEvaluationResult:
        """Evaluate experiment-based flag using ExperimentManager."""
        if context is None or not context.target_id:
            self._default_falls += 1
            return self._create_result(
                flag=flag,
                value=flag.default_value,
                result=EvaluationResult.NO_RULE,
                reason="no_target_id_for_experiment",
                matched_rule_id=None,
                start=start,
            )

        # Try ExperimentManager integration
        if self._experiment_manager is not None:
            metadata = flag.metadata or {}
            experiment_id = metadata.get("experiment_id", "")
            if experiment_id:
                variant = self._experiment_manager.assign(
                    experiment_id, context.target_id,
                )
                if variant is not None:
                    self._rule_match_count += 1
                    return self._create_result(
                        flag=flag,
                        value=variant.value,
                        result=EvaluationResult.HIT,
                        reason=f"experiment:{experiment_id}:{variant.variant_id}",
                        matched_rule_id=None,
                        start=start,
                    )

        # Fallback: use consistent hashing for experiment assignment
        for rule in flag.rules:
            if not rule.enabled:
                continue
            # Experiment rules use condition as group name
            # and value as the variant
            self._rule_match_count += 1
            return self._create_result(
                flag=flag,
                value=rule.value,
                result=EvaluationResult.HIT,
                reason=f"experiment:{rule.condition}",
                matched_rule_id=rule.rule_id,
                start=start,
            )

        self._default_falls += 1
        return self._create_result(
            flag=flag,
            value=flag.default_value,
            result=EvaluationResult.NO_RULE,
            reason="no_experiment_group",
            matched_rule_id=None,
            start=start,
        )

    async def _evaluate_canary(
        self,
        flag: FeatureFlag,
        context: Optional[FeatureContext],
        start: float,
    ) -> FeatureEvaluationResult:
        """Evaluate canary-based flag using CanaryManager."""
        if context is None or not context.target_id:
            self._default_falls += 1
            return self._create_result(
                flag=flag,
                value=flag.default_value,
                result=EvaluationResult.NO_RULE,
                reason="no_target_id_for_canary",
                matched_rule_id=None,
                start=start,
            )

        # Try CanaryManager integration
        if self._canary_manager is not None:
            deployment = self._canary_manager.get_deployment(flag.key)
            if deployment is not None and deployment.status == "running":
                percentage = deployment.current_percentage
                # Use consistent hashing to determine if target is in canary
                from .rollout import ConsistentHasher
                hasher = ConsistentHasher(algorithm="murmur3")
                if hasher.is_in_rollout(context.target_id, percentage):
                    # Record request for health monitoring
                    self._canary_manager.record_request(flag.key)
                    self._rule_match_count += 1
                    return self._create_result(
                        flag=flag,
                        value=True,
                        result=EvaluationResult.HIT,
                        reason=f"canary:{percentage}%",
                        matched_rule_id=None,
                        start=start,
                    )
                else:
                    self._default_falls += 1
                    return self._create_result(
                        flag=flag,
                        value=flag.default_value,
                        result=EvaluationResult.MISS,
                        reason=f"canary_not_in_rollout:{percentage}%",
                        matched_rule_id=None,
                        start=start,
                    )

        # Fallback: use rollout percentage from metadata
        metadata = flag.metadata or {}
        canary_percentage = metadata.get("canary_percentage")
        if canary_percentage is not None:
            try:
                percentage = float(canary_percentage)
                from .rollout import ConsistentHasher
                hasher = ConsistentHasher(algorithm="murmur3")
                if hasher.is_in_rollout(context.target_id, percentage):
                    self._rule_match_count += 1
                    return self._create_result(
                        flag=flag,
                        value=True,
                        result=EvaluationResult.HIT,
                        reason=f"canary:{percentage}%",
                        matched_rule_id=None,
                        start=start,
                    )
            except (ValueError, TypeError):
                pass

        self._default_falls += 1
        return self._create_result(
            flag=flag,
            value=flag.default_value,
            result=EvaluationResult.NO_RULE,
            reason="no_canary_deployment",
            matched_rule_id=None,
            start=start,
        )

    def set_canary_manager(self, manager: Any) -> None:
        """
        Set the canary manager for canary strategy evaluation.

        Args:
            manager: CanaryManager instance.
        """
        self._canary_manager = manager

    def set_experiment_manager(self, manager: Any) -> None:
        """
        Set the experiment manager for experiment strategy evaluation.

        Args:
            manager: ExperimentManager instance.
        """
        self._experiment_manager = manager

    def _rule_matches_impl(
        self,
        rule: FeatureRule,
        context: Optional[FeatureContext],
    ) -> bool:
        """
        Check if a rule condition matches the context.

        Supports simple attribute comparisons:
            - attribute == value
            - attribute != value
            - attribute in [values]

        Args:
            rule: Rule to evaluate.
            context: Evaluation context.

        Returns:
            True if the rule matches.
        """
        if rule.condition == "true":
            return True

        if context is None:
            return False

        condition = rule.condition.strip()

        # Check for attribute comparisons
        for operator, handler in [
            ("==", self._check_equals),
            ("!=", self._check_not_equals),
            (" in ", self._check_in_list),
            (" contains ", self._check_contains),
        ]:
            if operator in condition:
                parts = condition.split(operator, 1)
                if len(parts) == 2:
                    attr_name = parts[0].strip()
                    expected = parts[1].strip().strip("'\"[]")
                    actual = self._get_attribute(attr_name, context)
                    return handler(actual, expected)

        return False

    def _check_equals(
        self,
        actual: Any,
        expected: Any,
    ) -> bool:
        """Check if actual equals expected."""
        if actual is None:
            return expected.lower() == "none"
        return str(actual).lower() == str(expected).lower()

    def _check_not_equals(
        self,
        actual: Any,
        expected: Any,
    ) -> bool:
        """Check if actual does not equal expected."""
        return not self._check_equals(actual, expected)

    def _check_in_list(
        self,
        actual: Any,
        expected: str,
    ) -> bool:
        """Check if actual is in a comma-separated list."""
        values = [v.strip().strip("'\"") for v in expected.split(",")]
        return str(actual) in values

    def _check_contains(
        self,
        actual: Any,
        expected: str,
    ) -> bool:
        """Check if actual string contains expected."""
        if actual is None:
            return False
        return expected.lower() in str(actual).lower()

    def _get_attribute(
        self,
        attr_name: str,
        context: FeatureContext,
    ) -> Any:
        """Get an attribute value from the context."""
        # Check context attributes
        if hasattr(context, attr_name):
            return getattr(context, attr_name)

        # Check attributes dict
        return context.attributes.get(attr_name)

    def _create_result(
        self,
        flag: FeatureFlag,
        value: Any,
        result: EvaluationResult,
        reason: str,
        matched_rule_id: Optional[str],
        start: float,
        error: bool = False,
    ) -> FeatureEvaluationResult:
        """Create an evaluation result."""
        duration_ms = (time.perf_counter() - start) * 1000
        self._total_duration_ms += duration_ms

        return FeatureEvaluationResult(
            key=flag.key,
            value=value,
            enabled=flag.enabled,
            result=result,
            matched_rule_id=matched_rule_id,
            reason=reason,
            duration_ms=duration_ms,
        )

    def get_stats(self) -> Dict[str, Any]:
        """Get evaluator statistics."""
        total = self._evaluation_count
        avg_duration = self._total_duration_ms / total if total > 0 else 0.0
        return {
            "evaluations": self._evaluation_count,
            "errors": self._error_count,
            "error_rate": (self._error_count / total) if total > 0 else 0.0,
            "avg_duration_ms": avg_duration,
            "rule_matches": self._rule_match_count,
            "default_falls": self._default_falls,
            "match_rate": (self._rule_match_count / total) if total > 0 else 0.0,
        }

    def reset_stats(self) -> None:
        """Reset all evaluator statistics."""
        self._evaluation_count = 0
        self._error_count = 0
        self._total_duration_ms = 0.0
        self._rule_match_count = 0
        self._default_falls = 0