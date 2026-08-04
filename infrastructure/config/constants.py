"""
Configuration platform constants.

Defines fixed values for the configuration
platform including loader types, source
priorities, environment names, and default
settings.
"""

from __future__ import annotations

from enum import Enum


class LoaderType(str, Enum):
    """Supported configuration loader types."""

    YAML = "yaml"
    JSON = "json"
    TOML = "toml"
    ENV = "env"
    REMOTE = "remote"


class ConfigSource(str, Enum):
    """Configuration source priority order.

    Higher priority sources override
    lower priority sources when merged:

        CLI > ENV > SECRETS > REMOTE > FILE > DEFAULT
    """

    CLI = "cli"            # Highest priority
    ENV = "env"            # Environment variables
    SECRETS = "secrets"    # Secrets manager
    REMOTE = "remote"      # Remote config center
    FILE = "file"          # YAML/JSON/TOML files
    DEFAULT = "default"    # Default values (lowest)

    @property
    def priority(
        self,
    ) -> int:
        """Get source priority (higher = more important)."""

        priorities = {
            ConfigSource.CLI: 100,
            ConfigSource.ENV: 80,
            ConfigSource.SECRETS: 60,
            ConfigSource.REMOTE: 40,
            ConfigSource.FILE: 20,
            ConfigSource.DEFAULT: 0,
        }
        return priorities[self]


class Environment(str, Enum):
    """Deployment environment names."""

    DEVELOPMENT = "development"
    TESTING = "testing"
    STAGING = "staging"
    PRODUCTION = "production"


class ValidationLevel(str, Enum):
    """Configuration validation strictness."""

    NONE = "none"
    BASIC = "basic"
    STRICT = "strict"


# Default values
DEFAULT_ENVIRONMENT = Environment.DEVELOPMENT.value
DEFAULT_LOADER = LoaderType.YAML.value
DEFAULT_CACHE_TTL = 300  # seconds
DEFAULT_CONFIG_VERSION = 1

# Cache defaults
DEFAULT_CACHE_MAX_SIZE = 1000

# Validation defaults
DEFAULT_VALIDATION_LEVEL = ValidationLevel.BASIC

# Reload defaults
DEFAULT_RELOAD_INTERVAL = 30.0  # seconds
