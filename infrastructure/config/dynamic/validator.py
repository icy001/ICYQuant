"""
Dynamic configuration validator.

Validates configuration before hot reload activation.
Checks for:
- Required keys
- Type constraints
- Value ranges
- Cross-key dependencies
- Schema compliance
"""

from __future__ import annotations

import re
from typing import Any, Callable, Dict, List, Optional, Type


class DynamicValidator:
    """
    Validates configuration before activation.

    Extends the static validation framework with
    dynamic-specific checks for hot reload safety.

    Usage:
        validator = DynamicValidator()
        validator.add_required_key("server.port", int)
        validator.add_range_check("server.port", 1, 65535)

        errors = validator.validate(config_data)
        if not errors:
            # Safe to activate
    """

    def __init__(
        self,
    ) -> None:
        """Initialize dynamic validator."""
        self._required_keys: List[tuple] = []  # (key, type_optional)
        self._type_checks: Dict[str, Type] = {}
        self._range_checks: Dict[str, tuple] = {}  # (min, max)
        self._pattern_checks: Dict[str, str] = {}  # regex patterns
        self._dependency_checks: Dict[str, List[str]] = {}  # key -> required keys
        self._custom_validators: List[Callable] = []

    def add_required_key(
        self,
        key: str,
        expected_type: Optional[Type] = None,
    ) -> None:
        """
        Add a required configuration key.

        Args:
            key: Configuration key.
            expected_type: Expected value type.
        """
        self._required_keys.append((key, expected_type))

    def add_type_check(
        self,
        key: str,
        expected_type: Type,
    ) -> None:
        """
        Add a type constraint for a key.

        Args:
            key: Configuration key.
            expected_type: Expected value type.
        """
        self._type_checks[key] = expected_type

    def add_range_check(
        self,
        key: str,
        min_value: Any,
        max_value: Any,
    ) -> None:
        """
        Add a range constraint for a numeric key.

        Args:
            key: Configuration key.
            min_value: Minimum allowed value.
            max_value: Maximum allowed value.
        """
        self._range_checks[key] = (min_value, max_value)

    def add_pattern_check(
        self,
        key: str,
        pattern: str,
    ) -> None:
        """
        Add a regex pattern constraint for a key.

        Args:
            key: Configuration key.
            pattern: Regex pattern string.
        """
        self._pattern_checks[key] = pattern

    def add_dependency(
        self,
        key: str,
        requires: List[str],
    ) -> None:
        """
        Add a dependency constraint.

        Args:
            key: Configuration key.
            requires: List of keys that must also be present.
        """
        self._dependency_checks[key] = requires

    def add_validator(
        self,
        validator_func: Callable,
    ) -> None:
        """
        Add a custom validation function.

        Args:
            validator_func: Callable that takes config dict and returns
                            a list of error strings (empty if valid).
        """
        self._custom_validators.append(validator_func)

    def validate(
        self,
        config: Dict[str, Any],
    ) -> List[str]:
        """
        Validate configuration data.

        Args:
            config: Configuration dictionary.

        Returns:
            List of error messages (empty if valid).
        """
        errors: List[str] = []

        # Check required keys
        errors.extend(self._check_required(config))

        # Check types
        errors.extend(self._check_types(config))

        # Check ranges
        errors.extend(self._check_ranges(config))

        # Check patterns
        errors.extend(self._check_patterns(config))

        # Check dependencies
        errors.extend(self._check_dependencies(config))

        # Run custom validators
        for validator in self._custom_validators:
            try:
                result = validator(config)
                if result:
                    if isinstance(result, list):
                        errors.extend(result)
                    elif isinstance(result, str):
                        errors.append(result)
            except Exception as e:
                errors.append(f"Custom validator error: {e}")

        return errors

    def _check_required(
        self,
        config: Dict[str, Any],
    ) -> List[str]:
        """Check required keys are present and have correct types."""
        errors = []
        for key, expected_type in self._required_keys:
            if key not in config:
                errors.append(f"Missing required key: '{key}'")
                continue

            value = config[key]
            if value is None:
                errors.append(f"Required key '{key}' is null")
                continue

            if expected_type and not isinstance(value, expected_type):
                errors.append(
                    f"Key '{key}' expected type {expected_type.__name__}, "
                    f"got {type(value).__name__}"
                )

        return errors

    def _check_types(
        self,
        config: Dict[str, Any],
    ) -> List[str]:
        """Check type constraints."""
        errors = []
        for key, expected_type in self._type_checks.items():
            if key in config and config[key] is not None:
                value = config[key]
                if not isinstance(value, expected_type):
                    errors.append(
                        f"Key '{key}' must be {expected_type.__name__}, "
                        f"got {type(value).__name__}"
                    )
        return errors

    def _check_ranges(
        self,
        config: Dict[str, Any],
    ) -> List[str]:
        """Check range constraints."""
        errors = []
        for key, (min_val, max_val) in self._range_checks.items():
            if key in config and config[key] is not None:
                value = config[key]
                if isinstance(value, (int, float)):
                    if value < min_val or value > max_val:
                        errors.append(
                            f"Key '{key}' value {value} "
                            f"out of range [{min_val}, {max_val}]"
                        )
        return errors

    def _check_patterns(
        self,
        config: Dict[str, Any],
    ) -> List[str]:
        """Check regex pattern constraints."""
        errors = []
        for key, pattern in self._pattern_checks.items():
            if key in config and config[key] is not None:
                value = str(config[key])
                if not re.match(pattern, value):
                    errors.append(
                        f"Key '{key}' value '{value}' "
                        f"does not match pattern '{pattern}'"
                    )
        return errors

    def _check_dependencies(
        self,
        config: Dict[str, Any],
    ) -> List[str]:
        """Check cross-key dependencies."""
        errors = []
        for key, requires in self._dependency_checks.items():
            if key in config and config[key] is not None:
                for req_key in requires:
                    if req_key not in config or config[req_key] is None:
                        errors.append(
                            f"Key '{key}' requires '{req_key}' "
                            f"to be present and non-null"
                        )
        return errors

    def clear(
        self,
    ) -> None:
        """Clear all validation rules."""
        self._required_keys.clear()
        self._type_checks.clear()
        self._range_checks.clear()
        self._pattern_checks.clear()
        self._dependency_checks.clear()
        self._custom_validators.clear()
