"""
Configuration validation framework.

Provides a comprehensive validation framework
for configuration values, supporting:

- Schema Validation: Validate against expected schema
- Type Validation: Ensure values are correct types
- Range Validation: Check numeric ranges
- Dependency Validation: Verify required dependencies

The framework uses a chain-of-responsibility
pattern where multiple validators can be
chained together.

Usage:
    validator = ConfigurationValidator()
    validator.add_rule(TypeRule("server.port", int))
    validator.add_rule(RangeRule("server.port", min_value=1, max_value=65535))
    validator.add_rule(DependencyRule("server.ssl_cert", requires="server.ssl_enabled"))

    result = validator.validate(snapshot)
    if not result.valid:
        for error in result.errors:
            print(error)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, List, Optional, Type

from .models import ConfigurationSnapshot, ValidationResult


class ValidationRule(ABC):
    """
    Abstract validation rule.

    All validation rules inherit from this
    base class and implement the check() method.
    """

    @abstractmethod
    def check(
        self,
        snapshot: ConfigurationSnapshot,
    ) -> ValidationResult:
        """
        Check this rule against a snapshot.

        Args:
            snapshot: Configuration snapshot to validate.

        Returns:
            ValidationResult with any errors.
        """

        ...


# ── Type Validation ──


class TypeRule(ValidationRule):
    """Validate that a value has the expected type."""

    def __init__(
        self,
        key: str,
        expected_type: Type,
        required: bool = True,
    ) -> None:
        self.key = key
        self.expected_type = expected_type
        self.required = required

    def check(
        self,
        snapshot: ConfigurationSnapshot,
    ) -> ValidationResult:

        result = ValidationResult()
        value = snapshot.get(self.key)

        if value is None:
            if self.required:
                result.add_error(
                    f"Required key '{self.key}' is missing"
                )
            return result

        if not isinstance(value, self.expected_type):
            # Allow bool/int coercion for convenience
            if self.expected_type is int and isinstance(value, bool):
                pass  # bool is subclass of int, OK
            else:
                result.add_error(
                    f"Type mismatch for '{self.key}': "
                    f"expected {self.expected_type.__name__}, "
                    f"got {type(value).__name__}"
                )

        return result


# ── Range Validation ──


class RangeRule(ValidationRule):
    """Validate that a numeric value is within a range."""

    def __init__(
        self,
        key: str,
        min_value: Optional[Any] = None,
        max_value: Optional[Any] = None,
    ) -> None:
        self.key = key
        self.min_value = min_value
        self.max_value = max_value

    def check(
        self,
        snapshot: ConfigurationSnapshot,
    ) -> ValidationResult:

        result = ValidationResult()
        value = snapshot.get(self.key)

        if value is None:
            return result

        if not isinstance(value, (int, float)):
            result.add_warning(
                f"Range check skipped for '{self.key}': "
                f"not a numeric type"
            )
            return result

        if self.min_value is not None and value < self.min_value:
            result.add_error(
                f"Value for '{self.key}' ({value}) "
                f"is below minimum ({self.min_value})"
            )

        if self.max_value is not None and value > self.max_value:
            result.add_error(
                f"Value for '{self.key}' ({value}) "
                f"exceeds maximum ({self.max_value})"
            )

        return result


# ── Dependency Validation ──


class DependencyRule(ValidationRule):
    """Validate that a dependency is satisfied."""

    def __init__(
        self,
        key: str,
        requires: str,
    ) -> None:
        self.key = key
        self.requires = requires

    def check(
        self,
        snapshot: ConfigurationSnapshot,
    ) -> ValidationResult:

        result = ValidationResult()
        value = snapshot.get(self.key)

        # Only check dependency if the key exists
        if value is None:
            return result

        # Check if required dependency exists
        if not snapshot.contains(self.requires):
            result.add_error(
                f"Configuration dependency not satisfied: "
                f"'{self.key}' requires '{self.requires}'"
            )

        return result


# ── Schema Validation ──


class SchemaRule(ValidationRule):
    """Validate against a schema (dict of key -> type)."""

    def __init__(
        self,
        schema: dict,
    ) -> None:
        """
        Initialize schema rule.

        Args:
            schema: Dictionary mapping keys to expected types.
                    Example: {"port": int, "host": str, "debug": bool}
        """

        self.schema = schema

    def check(
        self,
        snapshot: ConfigurationSnapshot,
    ) -> ValidationResult:

        result = ValidationResult()

        for key, expected_type in self.schema.items():
            value = snapshot.get(key)

            if value is None:
                result.add_error(
                    f"Schema: required key '{key}' is missing"
                )
                continue

            if not isinstance(value, expected_type):
                result.add_error(
                    f"Schema: type mismatch for '{key}': "
                    f"expected {expected_type.__name__}, "
                    f"got {type(value).__name__}"
                )

        return result


# ── Choice Validation ──


class ChoiceRule(ValidationRule):
    """Validate that a value is one of allowed choices."""

    def __init__(
        self,
        key: str,
        choices: List[Any],
    ) -> None:
        self.key = key
        self.choices = choices

    def check(
        self,
        snapshot: ConfigurationSnapshot,
    ) -> ValidationResult:

        result = ValidationResult()
        value = snapshot.get(self.key)

        if value is None:
            return result

        if value not in self.choices:
            result.add_error(
                f"Value for '{self.key}' ({value}) "
                f"is not in allowed choices: {self.choices}"
            )

        return result


# ── Composite Validator ──


class ConfigurationValidator:
    """
    Configuration validator.

    Chains multiple validation rules and
    executes them against a configuration
    snapshot.

    Supported Rule Types:
    - TypeRule: Type checking
    - RangeRule: Numeric range checking
    - DependencyRule: Dependency verification
    - SchemaRule: Schema-based validation
    - ChoiceRule: Enumerated value validation

    Usage:
        validator = ConfigurationValidator()
        validator.add_rule(TypeRule("port", int))
        validator.add_rule(RangeRule("port", 1, 65535))

        result = validator.validate(snapshot)
    """

    def __init__(
        self,
    ) -> None:
        self._rules: List[ValidationRule] = []

    @property
    def rule_count(
        self,
    ) -> int:
        """Get number of registered rules."""
        return len(self._rules)

    def add_rule(
        self,
        rule: ValidationRule,
    ) -> None:
        """Add a validation rule."""

        self._rules.append(rule)

    def add_type_rule(
        self,
        key: str,
        expected_type: Type,
        required: bool = True,
    ) -> None:
        """Convenience: add a type rule."""

        self._rules.append(
            TypeRule(key, expected_type, required)
        )

    def add_range_rule(
        self,
        key: str,
        min_value: Optional[Any] = None,
        max_value: Optional[Any] = None,
    ) -> None:
        """Convenience: add a range rule."""

        self._rules.append(
            RangeRule(key, min_value, max_value)
        )

    def add_dependency_rule(
        self,
        key: str,
        requires: str,
    ) -> None:
        """Convenience: add a dependency rule."""

        self._rules.append(
            DependencyRule(key, requires)
        )

    def add_schema_rule(
        self,
        schema: dict,
    ) -> None:
        """Convenience: add a schema rule."""

        self._rules.append(SchemaRule(schema))

    def add_choice_rule(
        self,
        key: str,
        choices: List[Any],
    ) -> None:
        """Convenience: add a choice rule."""

        self._rules.append(ChoiceRule(key, choices))

    def validate(
        self,
        snapshot: ConfigurationSnapshot,
    ) -> ValidationResult:
        """
        Validate a configuration snapshot.

        Executes all registered rules and
        aggregates results.

        Args:
            snapshot: Configuration snapshot to validate.

        Returns:
            Aggregated ValidationResult.
        """

        if not self._rules:
            return ValidationResult(valid=True)

        result = ValidationResult()

        for rule in self._rules:
            try:
                rule_result = rule.check(snapshot)
                for error in rule_result.errors:
                    result.add_error(error)
                for warning in rule_result.warnings:
                    result.add_warning(warning)
            except Exception as e:
                result.add_error(
                    f"Validation rule failed: {type(rule).__name__} - {e}"
                )

        return result

    def clear(
        self,
    ) -> None:
        """Clear all rules."""

        self._rules.clear()
