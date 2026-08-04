"""
Configuration platform exceptions.

Defines the exception hierarchy for the
configuration platform, enabling precise
error handling for configuration-related
issues.
"""

from __future__ import annotations

from typing import List, Optional


class ConfigError(Exception):
    """Base exception for all configuration errors."""


class ConfigNotFoundError(ConfigError):
    """Raised when a configuration key is not found."""

    def __init__(
        self,
        key: str,
    ) -> None:
        self.key = key
        super().__init__(f"Configuration key not found: {key}")


class ConfigValidationError(ConfigError):
    """Raised when configuration validation fails."""

    def __init__(
        self,
        message: str,
        errors: Optional[List[str]] = None,
    ) -> None:
        self.errors = errors or []
        super().__init__(message)


class ConfigLoadError(ConfigError):
    """Raised when configuration loading fails."""

    def __init__(
        self,
        source: str,
        reason: str = "",
    ) -> None:
        self.source = source
        self.reason = reason
        msg = f"Failed to load configuration from: {source}"
        if reason:
            msg += f" ({reason})"
        super().__init__(msg)


class ConfigParseError(ConfigError):
    """Raised when configuration parsing fails."""

    def __init__(
        self,
        source: str,
        reason: str = "",
    ) -> None:
        self.source = source
        self.reason = reason
        msg = f"Failed to parse configuration from: {source}"
        if reason:
            msg += f" ({reason})"
        super().__init__(msg)


class ConfigTypeError(ConfigError):
    """Raised when a configuration value has an unexpected type."""

    def __init__(
        self,
        key: str,
        expected: str,
        actual: str,
    ) -> None:
        self.key = key
        self.expected = expected
        self.actual = actual
        super().__init__(
            f"Type mismatch for '{key}': "
            f"expected {expected}, got {actual}"
        )


class ConfigRangeError(ConfigError):
    """Raised when a configuration value is out of range."""

    def __init__(
        self,
        key: str,
        value,
        min_value=None,
        max_value=None,
    ) -> None:
        self.key = key
        self.value = value
        self.min_value = min_value
        self.max_value = max_value
        range_str = ""
        if min_value is not None and max_value is not None:
            range_str = f" (expected: {min_value}-{max_value})"
        elif min_value is not None:
            range_str = f" (min: {min_value})"
        elif max_value is not None:
            range_str = f" (max: {max_value})"
        super().__init__(
            f"Value out of range for '{key}': "
            f"{value}{range_str}"
        )


class ConfigDependencyError(ConfigError):
    """Raised when a configuration dependency is not satisfied."""

    def __init__(
        self,
        key: str,
        dependency: str,
    ) -> None:
        self.key = key
        self.dependency = dependency
        super().__init__(
            f"Configuration dependency not satisfied: "
            f"'{key}' requires '{dependency}'"
        )


class ConfigCacheError(ConfigError):
    """Raised when configuration cache operations fail."""


class ConfigSnapshotError(ConfigError):
    """Raised when configuration snapshot operations fail."""


class ConfigReloadError(ConfigError):
    """Raised when configuration reload fails."""

    def __init__(
        self,
        reason: str = "",
    ) -> None:
        self.reason = reason
        msg = "Configuration reload failed"
        if reason:
            msg += f": {reason}"
        super().__init__(msg)
