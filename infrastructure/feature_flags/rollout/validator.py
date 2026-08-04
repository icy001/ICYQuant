"""
Rollout policy validator.

Provides validation for rollout policies,
segment definitions, progressive stages,
and schedule configurations.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .rollout import (
    ProgressiveStage,
    RolloutAssignment,
    RolloutPolicy,
    SegmentDefinition,
)


class RolloutValidator:
    """
    Validator for rollout configurations.

    Ensures that rollout policies, segments,
    progressive stages, and schedules are
    properly configured before deployment.

    Usage:
        validator = RolloutValidator()
        errors = validator.validate_policy(policy)
        if errors:
            print("Invalid policy:", errors)
    """

    VALID_ALGORITHMS = ("murmur3", "sha256", "crc32")
    VALID_HASH_KEYS = (
        "account_id",
        "user_id",
        "strategy_id",
        "portfolio_id",
        "tenant_id",
    )
    VALID_OPERATORS = ("==", "!=", "IN", "NOT IN", "CONTAINS")
    VALID_SCHEDULE_FREQUENCIES = ("immediate", "daily", "weekly", "cron")

    def validate_policy(self, policy: RolloutPolicy) -> List[str]:
        """
        Validate a rollout policy.

        Args:
            policy: Policy to validate.

        Returns:
            List of validation error messages.
        """
        errors = []

        if not 0 <= policy.percentage <= 100:
            errors.append(
                f"Percentage must be 0-100, got {policy.percentage}",
            )

        if policy.algorithm not in self.VALID_ALGORITHMS:
            errors.append(
                f"Invalid algorithm: {policy.algorithm}. "
                f"Valid: {', '.join(self.VALID_ALGORITHMS)}",
            )

        if policy.max_buckets < 100:
            errors.append(
                f"max_buckets must be >= 100, got {policy.max_buckets}",
            )

        if policy.hash_key and not self._is_valid_hash_key(policy.hash_key):
            errors.append(
                f"Unknown hash_key: {policy.hash_key}. "
                f"Expected one of: {', '.join(self.VALID_HASH_KEYS)}",
            )

        return errors

    def validate_segment(self, segment: SegmentDefinition) -> List[str]:
        """
        Validate a segment definition.

        Args:
            segment: Segment to validate.

        Returns:
            List of validation error messages.
        """
        errors = []

        if not segment.segment_id:
            errors.append("segment_id is required")

        if not segment.attribute:
            errors.append("attribute is required")

        if segment.operator not in self.VALID_OPERATORS:
            errors.append(
                f"Invalid operator: {segment.operator}. "
                f"Valid: {', '.join(self.VALID_OPERATORS)}",
            )

        if not segment.values:
            errors.append("values list must not be empty")

        if segment.percentage is not None:
            if not 0 <= segment.percentage <= 100:
                errors.append(
                    f"Segment percentage must be 0-100, "
                    f"got {segment.percentage}",
                )

        return errors

    def validate_progressive_stages(
        self,
        stages: List[ProgressiveStage],
    ) -> List[str]:
        """
        Validate progressive rollout stages.

        Args:
            stages: List of stages.

        Returns:
            List of validation error messages.
        """
        errors = []

        if len(stages) < 2:
            errors.append("At least 2 stages required for progressive rollout")

        sorted_stages = sorted(stages, key=lambda s: s.percentage)
        for i in range(len(sorted_stages)):
            stage = sorted_stages[i]

            if not 0 <= stage.percentage <= 100:
                errors.append(
                    f"Stage {stage.stage_id}: percentage must be 0-100, "
                    f"got {stage.percentage}",
                )

            if stage.error_threshold < 0 or stage.error_threshold > 100:
                errors.append(
                    f"Stage {stage.stage_id}: error_threshold must be 0-100, "
                    f"got {stage.error_threshold}",
                )

            if stage.min_requests < 0:
                errors.append(
                    f"Stage {stage.stage_id}: min_requests must be >= 0",
                )

            if stage.delay_seconds < 0:
                errors.append(
                    f"Stage {stage.stage_id}: delay_seconds must be >= 0",
                )

        # Check for overlapping/decreasing percentages
        percentages = [s.percentage for s in stages]
        for i in range(len(percentages) - 1):
            if percentages[i] >= percentages[i + 1]:
                errors.append(
                    f"Stage {stages[i].stage_id} percentage "
                    f"({percentages[i]}) must be less than "
                    f"next stage ({percentages[i + 1]})",
                )

        return errors

    def validate_assignment(
        self,
        assignment: RolloutAssignment,
    ) -> List[str]:
        """
        Validate a rollout assignment.

        Args:
            assignment: Assignment to validate.

        Returns:
            List of validation error messages.
        """
        errors = []

        if not assignment.flag_key:
            errors.append("flag_key is required")

        if not assignment.target_id:
            errors.append("target_id is required")

        if not 0 <= assignment.percentage <= 100:
            errors.append(
                f"Percentage must be 0-100, got {assignment.percentage}",
            )

        if assignment.bucket < 0:
            errors.append(f"Bucket must be >= 0, got {assignment.bucket}")

        return errors

    def validate_policy_with_segments(
        self,
        policy: RolloutPolicy,
        segments: List[SegmentDefinition],
    ) -> List[str]:
        """
        Validate a policy together with its segments.

        Args:
            policy: Rollout policy.
            segments: Segment definitions.

        Returns:
            List of validation error messages.
        """
        errors = self.validate_policy(policy)

        for segment in segments:
            segment_errors = self.validate_segment(segment)
            for e in segment_errors:
                errors.append(f"[{segment.segment_id}] {e}")

        # Check for overlapping segments
        seen_attributes: Dict[str, List[str]] = {}
        for segment in segments:
            if not segment.enabled:
                continue
            attr = segment.attribute
            if attr not in seen_attributes:
                seen_attributes[attr] = []
            seen_attributes[attr].append(segment.segment_id)

        return errors

    def _is_valid_hash_key(self, key: str) -> bool:
        """Check if a hash key is valid."""
        if key in self.VALID_HASH_KEYS:
            return True
        # Also allow custom keys for flexibility
        return len(key) > 0 and len(key) <= 64

    def validate_all(
        self,
        policy: Optional[RolloutPolicy] = None,
        segments: Optional[List[SegmentDefinition]] = None,
        stages: Optional[List[ProgressiveStage]] = None,
    ) -> Dict[str, List[str]]:
        """
        Run all validations and return grouped errors.

        Args:
            policy: Policy to validate.
            segments: Segments to validate.
            stages: Stages to validate.

        Returns:
            Dict of category → errors mapping.
        """
        result: Dict[str, List[str]] = {}

        if policy:
            result["policy"] = self.validate_policy(policy)

        if segments:
            result["segments"] = []
            for segment in segments:
                errors = self.validate_segment(segment)
                for e in errors:
                    result["segments"].append(
                        f"[{segment.segment_id}] {e}",
                    )

        if stages:
            result["stages"] = self.validate_progressive_stages(stages)

        return {k: v for k, v in result.items() if v}
