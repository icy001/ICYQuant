"""
Feature flag platform models.

Defines the core data structures for
feature flags, evaluation results,
audit entries, and context objects.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from .constants import (
    EvaluationResult,
    EvaluationStrategy,
    FeatureFlagType,
    FlagStatus,
    OperatorAction,
)


@dataclass(frozen=True)
class FeatureFlag:
    """
    An immutable feature flag definition.

    Represents a single feature toggle with its
    metadata, evaluation rules, and targeting
    configuration.

    Attributes:
        key: Unique flag identifier (e.g. "trading.new_risk_model").
        enabled: Whether the flag is currently active.
        description: Human-readable description.
        flag_type: Type of the flag (boolean, variant, rollout, etc).
        strategy: Evaluation strategy to use.
        default_value: Default value when no rule matches.
        tags: Tags for categorization and filtering.
        metadata: Additional key-value metadata.
        rules: Targeting rules for conditional evaluation.
        status: Lifecycle status of the flag.
        created_at: Creation timestamp.
        updated_at: Last update timestamp.
        owner: Flag owner/team.
        expires_at: Optional expiration timestamp.
    """

    key: str
    enabled: bool
    description: str
    flag_type: FeatureFlagType = FeatureFlagType.BOOLEAN
    strategy: EvaluationStrategy = EvaluationStrategy.STATIC
    default_value: Any = True
    tags: frozenset[str] = field(default_factory=frozenset)
    metadata: Dict[str, Any] = field(default_factory=dict)
    rules: List["FeatureRule"] = field(default_factory=list)
    status: FlagStatus = FlagStatus.ACTIVE
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    owner: str = ""
    expires_at: Optional[datetime] = None


@dataclass(frozen=True)
class FeatureRule:
    """
    An immutable evaluation rule for a feature flag.

    Rules are evaluated in priority order. The first
    matching rule determines the flag's value.

    Attributes:
        rule_id: Unique rule identifier.
        priority: Evaluation priority (lower = first).
        condition: Condition expression (e.g. "user.role == 'admin'").
        value: Value to return when the rule matches.
        enabled: Whether this rule is active.
        description: Human-readable rule description.
        tags: Tags for categorization.
    """

    rule_id: str
    priority: int = 0
    condition: str = "true"
    value: Any = True
    enabled: bool = True
    description: str = ""
    tags: frozenset[str] = field(default_factory=frozenset)


@dataclass(frozen=True)
class FeatureContext:
    """
    Context object for feature flag evaluation.

    Contains all relevant attributes that may
    be used in targeting rules (user, account,
    environment, etc).

    Attributes:
        target_id: Target identifier (user/account/strategy ID).
        target_type: Type of target (user, account, strategy).
        attributes: Arbitrary context attributes for rule evaluation.
        environment: Deployment environment name.
        request_id: Trace ID for request correlation.
    """

    target_id: str = ""
    target_type: str = ""
    attributes: Dict[str, Any] = field(default_factory=dict)
    environment: str = "development"
    request_id: str = ""


@dataclass
class FeatureEvaluationResult:
    """
    Result of a feature flag evaluation.

    Attributes:
        key: Flag key that was evaluated.
        value: Evaluated flag value.
        enabled: Whether the flag is enabled.
        result: Evaluation result status.
        matched_rule_id: ID of the matching rule (if any).
        reason: Reason for the result (e.g. "rule matched", "default").
        duration_ms: Evaluation duration in milliseconds.
        timestamp: When the evaluation occurred.
    """

    key: str
    value: Any
    enabled: bool
    result: EvaluationResult = EvaluationResult.HIT
    matched_rule_id: Optional[str] = None
    reason: str = ""
    duration_ms: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class AuditEntry:
    """
    An audit log entry for feature flag changes.

    Attributes:
        entry_id: Unique entry identifier.
        action: Action performed (create, update, delete, etc).
        flag_key: Feature flag key.
        operator: Who performed the action.
        old_value: Previous value (for updates).
        new_value: New value (for updates).
        reason: Reason for the change.
        trace_id: Correlation trace ID.
        metadata: Additional metadata.
        timestamp: When the action occurred.
    """

    entry_id: str = ""
    action: OperatorAction = OperatorAction.EVALUATE
    flag_key: str = ""
    operator: str = "system"
    old_value: Any = None
    new_value: Any = None
    reason: str = ""
    trace_id: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class FeatureFlagCacheEntry:
    """
    A cached feature flag value with metadata.

    Attributes:
        key: Flag key.
        value: Cached value.
        version: Version counter for invalidation.
        expires_at: TTL expiration timestamp.
        cached_at: When the entry was created.
    """

    key: str = ""
    value: Any = None
    version: int = 0
    expires_at: Optional[datetime] = None
    cached_at: datetime = field(default_factory=datetime.utcnow)