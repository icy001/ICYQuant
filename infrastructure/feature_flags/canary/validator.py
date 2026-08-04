"""
Canary release validation.

Validates canary deployment configurations
including stages, policies, and health thresholds.
"""

from __future__ import annotations

from typing import Any, Dict, List

from .policy import CanaryPolicy
from .stage import CanaryDeployment, CanaryStage


class CanaryValidator:
    """
    Validator for canary configurations.

    Usage:
        validator = CanaryValidator()
        errors = validator.validate_stages(stages)
        if errors:
            print("Invalid:", errors)
    """

    def validate_stage(self, stage: CanaryStage) -> List[str]:
        """Validate a single canary stage."""
        errors = []
        if not stage.stage_id:
            errors.append("stage_id is required")
        if not 0 <= stage.percentage <= 100:
            errors.append(f"Percentage must be 0-100, got {stage.percentage}")
        if not 0 <= stage.health_threshold <= 100:
            errors.append(f"Health threshold must be 0-100, got {stage.health_threshold}")
        if not 0 <= stage.error_rate_threshold <= 100:
            errors.append(
                f"Error rate threshold must be 0-100, got {stage.error_rate_threshold}"
            )
        if stage.latency_p99_threshold_ms < 0:
            errors.append("Latency threshold must be >= 0")
        return errors

    def validate_stages(self, stages: List[CanaryStage]) -> List[str]:
        """Validate a list of canary stages."""
        errors = []
        if len(stages) < 2:
            errors.append("At least 2 stages required")
        for i, stage in enumerate(stages):
            stage_errors = self.validate_stage(stage)
            for e in stage_errors:
                errors.append(f"[{stage.stage_id or i}] {e}")
        # Check ordering
        for i in range(len(stages) - 1):
            if stages[i].percentage >= stages[i + 1].percentage:
                errors.append(
                    f"Stage {stages[i].stage_id} percentage "
                    f"({stages[i].percentage}) must be less than "
                    f"next stage ({stages[i + 1].percentage})"
                )
        return errors

    def validate_policy(self, policy: CanaryPolicy) -> List[str]:
        """Validate a canary policy."""
        errors = []
        valid_strategies = ("conservative", "balanced", "aggressive")
        if policy.strategy not in valid_strategies:
            errors.append(
                f"Invalid strategy: {policy.strategy}. "
                f"Valid: {', '.join(valid_strategies)}"
            )
        if not 0 <= policy.rollback_threshold <= 100:
            errors.append(f"Rollback threshold must be 0-100, got {policy.rollback_threshold}")
        if policy.min_sample_size < 0:
            errors.append("Min sample size must be >= 0")
        return errors

    def validate_deployment(self, deployment: CanaryDeployment) -> List[str]:
        """Validate a canary deployment."""
        errors = []
        if not deployment.feature_key:
            errors.append("feature_key is required")
        stage_errors = self.validate_stages(deployment.stages)
        errors.extend(stage_errors)
        if deployment.current_stage_index < 0:
            errors.append("current_stage_index must be >= 0")
        if deployment.current_stage_index >= len(deployment.stages):
            errors.append("current_stage_index out of range")
        return errors
