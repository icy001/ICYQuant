"""
Feature flag platform validator.

Provides validation logic for feature flag
definitions, rules, and configurations. Ensures
data integrity before flags are registered and
rules are evaluated.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from .constants import (
    DEFAULT_MAX_RULES_PER_FLAG,
    EvaluationStrategy,
    FeatureFlagType,
    FlagStatus,
)
from .exceptions import FeatureFlagValidationError
from .models import FeatureContext, FeatureFlag, FeatureRule
from .utils import sanitize_flag_key

logger = logging.getLogger(__name__)


class FeatureFlagValidator:
    """
    Validates feature flag definitions and configurations.

    Ensures data integrity by checking flag keys,
    types, rules, context objects, and configuration
    values before they are accepted by the platform.

    Usage:
        validator = FeatureFlagValidator()
        errors = validator.validate_flag(my_flag)
        if not errors:
            # Flag is valid
    """

    # Valid attribute comparison operators
    VALID_OPERATORS = ("==", "!=", " in ", " contains ")

    # Required fields for a valid flag
    REQUIRED_FLAG_FIELDS = ("key", "enabled", "description")

    # Maximum lengths
    MAX_KEY_LENGTH = 256
    MAX_DESCRIPTION_LENGTH = 1024
    MAX_RULES_PER_FLAG = DEFAULT_MAX_RULES_PER_FLAG
    MAX_METADATA_KEYS = 64
    MAX_TAGS = 32

    # Valid flag key pattern: starts with letter, then lowercase alphanumeric/dots/hyphens/underscores
    KEY_PATTERN = re.compile(r"^[a-z][a-z0-9._-]*$")

    def __init__(
        self,
        max_rules_per_flag: int = DEFAULT_MAX_RULES_PER_FLAG,
    ) -> None:
        """
        Initialize the validator.

        Args:
            max_rules_per_flag: Maximum allowed rules per flag.
        """
        self._max_rules = max_rules_per_flag
        self._total_validated = 0
        self._total_errors = 0

    def validate_flag(
        self,
        flag: FeatureFlag,
    ) -> List[str]:
        """
        Validate a complete feature flag definition.

        Checks all aspects of the flag including:
            - Key format and length
            - Flag type and strategy compatibility
            - Rules validity
            - Metadata constraints
            - Status validity

        Args:
            flag: Feature flag to validate.

        Returns:
            List of validation error messages (empty if valid).
        """
        errors: List[str] = []

        # Validate key
        errors.extend(self._validate_key(flag.key))

        # Validate description
        if not flag.description:
            errors.append("Description is required")
        elif len(flag.description) > self.MAX_DESCRIPTION_LENGTH:
            errors.append(
                f"Description exceeds max length "
                f"({len(flag.description)}/{self.MAX_DESCRIPTION_LENGTH})"
            )

        # Validate type and strategy compatibility
        errors.extend(
            self._validate_type_strategy(flag.flag_type, flag.strategy)
        )

        # Validate rules
        if flag.rules:
            if len(flag.rules) > self._max_rules:
                errors.append(
                    f"Too many rules ({len(flag.rules)}/{self._max_rules})"
                )
            for rule in flag.rules:
                rule_errors = self._validate_rule(rule)
                errors.extend(rule_errors)

        # Validate metadata
        errors.extend(self._validate_metadata(flag.metadata))

        # Validate tags
        if len(flag.tags) > self.MAX_TAGS:
            errors.append(
                f"Too many tags ({len(flag.tags)}/{self.MAX_TAGS})"
            )

        # Validate status
        if flag.status not in list(FlagStatus):
            errors.append(f"Invalid status: {flag.status}")

        # Validate expiration
        if flag.expires_at and flag.created_at:
            if flag.expires_at < flag.created_at:
                errors.append(
                    "Expiration time must be after creation time"
                )

        self._total_validated += 1
        if errors:
            self._total_errors += 1
            logger.debug(
                "Validation failed for flag %s: %s",
                flag.key, errors,
            )

        return errors

    def validate_flag_key(
        self,
        key: str,
    ) -> List[str]:
        """
        Validate a feature flag key string.

        Args:
            key: Flag key to validate.

        Returns:
            List of validation errors.
        """
        return self._validate_key(key)

    def validate_context(
        self,
        context: FeatureContext,
    ) -> List[str]:
        """
        Validate an evaluation context.

        Args:
            context: Context to validate.

        Returns:
            List of validation errors.
        """
        errors: List[str] = []

        if context.target_type and not context.target_id:
            errors.append(
                "target_id is required when target_type is specified"
            )

        if context.attributes:
            for key in context.attributes:
                if not isinstance(key, str):
                    errors.append(
                        f"Attribute key must be string: {key}"
                    )

        if context.request_id and len(context.request_id) > 256:
            errors.append(
                "request_id exceeds max length (256)"
            )

        return errors

    def validate_config(
        self,
        config: Dict[str, Any],
    ) -> List[str]:
        """
        Validate configuration values.

        Args:
            config: Configuration dictionary.

        Returns:
            List of validation errors.
        """
        errors: List[str] = []

        cache_ttl = config.get("cache_ttl", 60)
        if not isinstance(cache_ttl, int) or cache_ttl < 1:
            errors.append("cache_ttl must be a positive integer")
        elif cache_ttl > 3600:
            errors.append("cache_ttl must be <= 3600 seconds")

        cache_max = config.get("cache_max_size", 1024)
        if not isinstance(cache_max, int) or cache_max < 1:
            errors.append("cache_max_size must be a positive integer")

        audit_max = config.get("audit_max_entries", 10000)
        if not isinstance(audit_max, int) or audit_max < 100:
            errors.append("audit_max_entries must be >= 100")

        return errors

    def validate_rule(
        self,
        rule: FeatureRule,
    ) -> List[str]:
        """
        Validate a single feature rule.

        Args:
            rule: Rule to validate.

        Returns:
            List of validation errors.
        """
        return self._validate_rule(rule)

    def _validate_key(
        self,
        key: str,
    ) -> List[str]:
        """Validate flag key format."""
        errors: List[str] = []

        if not key:
            errors.append("Key is required")
            return errors

        if not isinstance(key, str):
            errors.append("Key must be a string")
            return errors

        if len(key) > self.MAX_KEY_LENGTH:
            errors.append(
                f"Key exceeds max length "
                f"({len(key)}/{self.MAX_KEY_LENGTH})"
            )

        if not self.KEY_PATTERN.match(key):
            errors.append(
                f"Key must start with a letter and contain only "
                f"lowercase letters, digits, dots, hyphens, underscores"
            )

        try:
            sanitize_flag_key(key)
        except ValueError as e:
            errors.append(str(e))

        return errors

    def _validate_type_strategy(
        self,
        flag_type: FeatureFlagType,
        strategy: EvaluationStrategy,
    ) -> List[str]:
        """Validate type and strategy compatibility."""
        errors: List[str] = []

        # Boolean flags should use static or rule-based
        if flag_type == FeatureFlagType.BOOLEAN:
            if strategy not in (
                EvaluationStrategy.STATIC,
                EvaluationStrategy.RULE_BASED,
            ):
                errors.append(
                    f"Boolean flags should use static or rule_based strategy, "
                    f"got {strategy.value}"
                )

        # Percentage rollout flags should use percentage strategy
        if flag_type == FeatureFlagType.ROLLOUT:
            if strategy not in (
                EvaluationStrategy.PERCENTAGE,
                EvaluationStrategy.RULE_BASED,
            ):
                errors.append(
                    f"Rollout flags should use percentage strategy, "
                    f"got {strategy.value}"
                )

        # Kill switch flags should use static strategy
        if flag_type == FeatureFlagType.KILL_SWITCH:
            if strategy != EvaluationStrategy.STATIC:
                errors.append(
                    f"Kill switch flags should use static strategy, "
                    f"got {strategy.value}"
                )

        return errors

    def _validate_rule(
        self,
        rule: FeatureRule,
    ) -> List[str]:
        """Validate a single rule."""
        errors: List[str] = []

        if not rule.rule_id:
            errors.append("Rule ID is required")

        if not isinstance(rule.priority, int):
            errors.append("Rule priority must be an integer")

        condition = rule.condition.strip() if rule.condition else "true"

        # Allow numeric conditions (for percentage rollout)
        try:
            float(condition)
            is_numeric = True
        except (ValueError, TypeError):
            is_numeric = False

        # Check if condition uses valid operators
        if (
            condition != "true"
            and "false" not in condition
            and not is_numeric
        ):
            has_valid_operator = any(
                op in condition for op in self.VALID_OPERATORS
            )
            if not has_valid_operator:
                # Allow simple conditions like attribute names
                if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", condition):
                    errors.append(
                        f"Invalid rule condition: {condition}"
                    )

        return errors

    def _validate_metadata(
        self,
        metadata: Dict[str, Any],
    ) -> List[str]:
        """Validate metadata dictionary."""
        errors: List[str] = []

        if not metadata:
            return errors

        if len(metadata) > self.MAX_METADATA_KEYS:
            errors.append(
                f"Too many metadata keys "
                f"({len(metadata)}/{self.MAX_METADATA_KEYS})"
            )

        for key, value in metadata.items():
            if not isinstance(key, str):
                errors.append(f"Metadata key must be string: {key}")
            if key.startswith("_"):
                errors.append(
                    f"Metadata key cannot start with underscore: {key}"
                )

        return errors

    def get_stats(self) -> Dict[str, Any]:
        """Get validator statistics."""
        total = self._total_validated
        return {
            "total_validated": total,
            "total_errors": self._total_errors,
            "error_rate": (
                self._total_errors / total if total > 0 else 0.0
            ),
        }