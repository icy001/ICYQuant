"""
Feature flag platform constants.

Defines fixed values for the feature flag
platform including flag types, evaluation
strategies, and default settings.
"""

from __future__ import annotations

from enum import Enum


class FeatureFlagType(str, Enum):
    """Supported feature flag types."""

    BOOLEAN = "boolean"
    VARIANT = "variant"
    ROLLOUT = "rollout"
    PERCENTAGE = "percentage"
    KILL_SWITCH = "kill_switch"


class EvaluationStrategy(str, Enum):
    """Feature flag evaluation strategies."""

    STATIC = "static"
    RULE_BASED = "rule_based"
    PERCENTAGE = "percentage"
    EXPERIMENT = "experiment"
    CANARY = "canary"


class FlagStatus(str, Enum):
    """Feature flag lifecycle status."""

    DRAFT = "draft"
    ACTIVE = "active"
    INACTIVE = "inactive"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"


class StorageBackend(str, Enum):
    """Supported storage backend types."""

    MEMORY = "memory"
    YAML = "yaml"
    DATABASE = "database"
    REDIS = "redis"
    REMOTE = "remote"


class OperatorAction(str, Enum):
    """Audit log operator actions."""

    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    ENABLE = "enable"
    DISABLE = "disable"
    EVALUATE = "evaluate"
    ROLLBACK = "rollback"


class EvaluationResult(str, Enum):
    """Evaluation result status."""

    HIT = "hit"
    MISS = "miss"
    ERROR = "error"
    NO_RULE = "no_rule"


DEFAULT_CACHE_TTL = 60
DEFAULT_CACHE_MAX_SIZE = 1024
DEFAULT_STORAGE_BACKEND = StorageBackend.MEMORY
DEFAULT_STRATEGY = EvaluationStrategy.STATIC
DEFAULT_FLAG_TYPE = FeatureFlagType.BOOLEAN
DEFAULT_MAX_RULES_PER_FLAG = 20
DEFAULT_EVAL_TIMEOUT_SECONDS = 5