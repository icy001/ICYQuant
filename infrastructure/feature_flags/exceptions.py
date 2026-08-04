"""
Feature flag platform exceptions.

Defines the exception hierarchy for the
feature flag platform, enabling precise
error handling for flag evaluation and
management issues.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


class FeatureFlagError(Exception):
    """Base exception for all feature flag errors."""


class FeatureFlagNotFoundError(FeatureFlagError):
    """Raised when a feature flag key is not found."""

    def __init__(
        self,
        key: str,
    ) -> None:
        self.key = key
        super().__init__(f"Feature flag not found: {key}")


class FeatureFlagAlreadyExistsError(FeatureFlagError):
    """Raised when registering a duplicate feature flag."""

    def __init__(
        self,
        key: str,
    ) -> None:
        self.key = key
        super().__init__(f"Feature flag already exists: {key}")


class FeatureFlagValidationError(FeatureFlagError):
    """Raised when feature flag validation fails."""

    def __init__(
        self,
        message: str,
        errors: Optional[List[str]] = None,
    ) -> None:
        self.errors = errors or []
        super().__init__(message)


class FeatureFlagEvaluationError(FeatureFlagError):
    """Raised when flag evaluation fails."""

    def __init__(
        self,
        key: str,
        reason: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.key = key
        self.reason = reason
        self.context = context or {}
        super().__init__(f"Feature flag evaluation failed [{key}]: {reason}")


class FeatureFlagStorageError(FeatureFlagError):
    """Raised when storage operations fail."""

    def __init__(
        self,
        operation: str,
        backend: str,
        reason: str,
    ) -> None:
        self.operation = operation
        self.backend = backend
        self.reason = reason
        super().__init__(
            f"Storage operation failed [{operation}@{backend}]: {reason}",
        )


class FeatureFlagCacheError(FeatureFlagError):
    """Raised when cache operations fail."""

    def __init__(
        self,
        operation: str,
        key: str,
        reason: str,
    ) -> None:
        self.operation = operation
        self.key = key
        self.reason = reason
        super().__init__(
            f"Cache operation failed [{operation}@{key}]: {reason}",
        )


class FeatureFlagCircuitError(FeatureFlagError):
    """Raised when circuit breaker blocks evaluation."""

    def __init__(
        self,
        key: str,
    ) -> None:
        self.key = key
        super().__init__(
            f"Circuit breaker open for feature flag: {key}",
        )


class TargetingRuleError(FeatureFlagError):
    """Base exception for targeting rule errors."""

    def __init__(
        self,
        message: str,
        rule_id: str = "",
    ) -> None:
        self.rule_id = rule_id
        super().__init__(message)


class TargetingRuleParseError(TargetingRuleError):
    """Raised when a rule expression fails to parse."""

    def __init__(
        self,
        expression: str,
        reason: str,
        position: int = -1,
    ) -> None:
        self.expression = expression
        self.reason = reason
        self.position = position
        super().__init__(
            f"Parse error in expression '{expression}': {reason} "
            f"at position {position}",
        )


class TargetingRuleCompileError(TargetingRuleError):
    """Raised when a rule fails to compile."""

    def __init__(
        self,
        rule_id: str,
        reason: str,
    ) -> None:
        super().__init__(
            f"Compile error in rule '{rule_id}': {reason}",
            rule_id=rule_id,
        )


class TargetingRuleEvalError(TargetingRuleError):
    """Raised when a rule evaluation fails."""

    def __init__(
        self,
        rule_id: str,
        reason: str,
    ) -> None:
        super().__init__(
            f"Evaluation error in rule '{rule_id}': {reason}",
            rule_id=rule_id,
        )


# ── Rollout Exceptions ──


class RolloutError(FeatureFlagError):
    """Base exception for rollout errors."""

    def __init__(
        self,
        message: str,
        flag_key: str = "",
    ) -> None:
        self.flag_key = flag_key
        super().__init__(message)


class RolloutPolicyError(RolloutError):
    """Raised when a rollout policy is invalid."""

    def __init__(
        self,
        flag_key: str,
        reason: str,
    ) -> None:
        super().__init__(
            f"Rollout policy error for '{flag_key}': {reason}",
            flag_key=flag_key,
        )


class RolloutAssignmentError(RolloutError):
    """Raised when a rollout assignment fails."""

    def __init__(
        self,
        flag_key: str,
        target_id: str,
        reason: str,
    ) -> None:
        self.target_id = target_id
        super().__init__(
            f"Rollout assignment failed for '{flag_key}' target '{target_id}': {reason}",
            flag_key=flag_key,
        )


class ProgressiveRolloutError(RolloutError):
    """Raised when progressive rollout fails."""

    def __init__(
        self,
        flag_key: str,
        stage: int,
        reason: str,
    ) -> None:
        self.stage = stage
        super().__init__(
            f"Progressive rollout error for '{flag_key}' at stage {stage}: {reason}",
            flag_key=flag_key,
        )


class SegmentMatchError(RolloutError):
    """Raised when segment matching fails."""

    def __init__(
        self,
        flag_key: str,
        reason: str,
    ) -> None:
        super().__init__(
            f"Segment match error for '{flag_key}': {reason}",
            flag_key=flag_key,
        )


# ── Canary Exceptions ──


class CanaryError(FeatureFlagError):
    """Base exception for canary release errors."""

    def __init__(
        self,
        message: str,
        feature_key: str = "",
    ) -> None:
        self.feature_key = feature_key
        super().__init__(message)


class CanaryDeploymentError(CanaryError):
    """Raised when a canary deployment operation fails."""

    def __init__(
        self,
        feature_key: str,
        reason: str,
    ) -> None:
        super().__init__(
            f"Canary deployment error for '{feature_key}': {reason}",
            feature_key=feature_key,
        )


class CanaryHealthError(CanaryError):
    """Raised when a canary health check fails."""

    def __init__(
        self,
        feature_key: str,
        status: str,
        score: float,
    ) -> None:
        self.health_status = status
        self.health_score = score
        super().__init__(
            f"Canary health check failed for '{feature_key}': "
            f"status={status}, score={score:.1f}",
            feature_key=feature_key,
        )


class CanaryPromotionError(CanaryError):
    """Raised when a canary promotion fails."""

    def __init__(
        self,
        feature_key: str,
        reason: str,
    ) -> None:
        super().__init__(
            f"Canary promotion failed for '{feature_key}': {reason}",
            feature_key=feature_key,
        )


class CanaryRollbackError(CanaryError):
    """Raised when a canary rollback fails."""

    def __init__(
        self,
        feature_key: str,
        reason: str,
    ) -> None:
        super().__init__(
            f"Canary rollback failed for '{feature_key}': {reason}",
            feature_key=feature_key,
        )


# ── Experiment Exceptions ──


class ExperimentError(FeatureFlagError):
    """Base exception for experiment errors."""

    def __init__(
        self,
        message: str,
        experiment_id: str = "",
    ) -> None:
        self.experiment_id = experiment_id
        super().__init__(message)


class ExperimentNotFoundError(ExperimentError):
    """Raised when an experiment is not found."""

    def __init__(
        self,
        experiment_id: str,
    ) -> None:
        super().__init__(
            f"Experiment not found: {experiment_id}",
            experiment_id=experiment_id,
        )


class ExperimentValidationError(ExperimentError):
    """Raised when experiment validation fails."""

    def __init__(
        self,
        experiment_id: str,
        errors: Optional[List[str]] = None,
    ) -> None:
        self.errors = errors or []
        super().__init__(
            f"Experiment validation failed for '{experiment_id}': "
            f"{'; '.join(self.errors)}",
            experiment_id=experiment_id,
        )


class ExperimentAllocationError(ExperimentError):
    """Raised when variant allocation fails."""

    def __init__(
        self,
        experiment_id: str,
        target_id: str,
        reason: str,
    ) -> None:
        self.target_id = target_id
        super().__init__(
            f"Variant allocation failed for experiment '{experiment_id}' "
            f"target '{target_id}': {reason}",
            experiment_id=experiment_id,
        )


class ExperimentAnalysisError(ExperimentError):
    """Raised when statistical analysis fails."""

    def __init__(
        self,
        experiment_id: str,
        reason: str,
    ) -> None:
        super().__init__(
            f"Experiment analysis failed for '{experiment_id}': {reason}",
            experiment_id=experiment_id,
        )