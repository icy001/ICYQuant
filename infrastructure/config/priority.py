"""
Configuration Priority Definitions.

Defines the priority order for configuration sources.
Higher priority sources will override lower priority ones.
"""

from enum import IntEnum


class ConfigurationPriority(IntEnum):
    """
    Priority for configuration sources.

    Higher value means higher priority (overrides lower ones).
    Default = 10 (lowest) < ... < CLI = 80 (highest)
    """

    DEFAULT = 10
    YAML = 20
    TOML = 30
    JSON = 40
    REMOTE = 50
    SECRETS = 60
    ENV = 70
    CLI = 80


class MergeStrategy:
    """Enumeration for merge strategies."""
    FLAT = "flat"
    RECURSIVE = "recursive"
    LIST_REPLACE = "list_replace"
    LIST_APPEND = "list_append"
    DEEP = "deep"
