"""
Secrets platform data models.

Defines the core data structures for
secrets management, including secret items,
metadata, and access entries.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from .constants import SecretCategory, SecretFormat, SecretStatus


@dataclass(frozen=True)
class SecretItem:
    """
    Immutable secret item.

    Represents a single secret entry with its
    value, metadata, and lifecycle information.

    Attributes:
        key: The secret key (path).
        value: The secret value.
        provider: Source provider name.
        version: Monotonically increasing version number.
        created_at: Creation timestamp.
        expires_at: Optional expiration timestamp.
        readonly: If True, secret cannot be modified.
        category: Secret category classification.
        format: Value format.
        namespace: Namespace for isolation.
        checksum: Value checksum for integrity.
        metadata: Additional metadata dict.
    """

    key: str
    value: str
    provider: str = "local"
    version: int = 1
    created_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    readonly: bool = True
    category: SecretCategory = SecretCategory.OTHER
    format: SecretFormat = SecretFormat.PLAINTEXT
    namespace: str = "default"
    checksum: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_expired(self) -> bool:
        """Check if the secret has expired."""
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at

    @property
    def age_days(self) -> float:
        """Get secret age in days."""
        delta = datetime.utcnow() - self.created_at
        return delta.total_seconds() / 86400.0

    def to_dict(self, mask_value: bool = False) -> Dict[str, Any]:
        """
        Convert to dictionary.

        Args:
            mask_value: If True, mask the value.

        Returns:
            Dictionary representation.
        """
        from .utils import mask_secret_value

        value = self.value
        if mask_value:
            value = mask_secret_value(self.value)

        return {
            "key": self.key,
            "value": value,
            "provider": self.provider,
            "version": self.version,
            "created_at": self.created_at.isoformat() + "Z",
            "expires_at": self.expires_at.isoformat() + "Z" if self.expires_at else None,
            "readonly": self.readonly,
            "category": self.category.value,
            "format": self.format.value,
            "namespace": self.namespace,
            "checksum": self.checksum,
            "metadata": self.metadata,
        }


@dataclass(frozen=True)
class SecretMetadata:
    """
    Secret metadata entry.

    Contains metadata about a secret without
    exposing the secret value itself.

    Attributes:
        key: The secret key.
        provider: Source provider name.
        version: Current version number.
        status: Secret lifecycle status.
        created_at: Creation timestamp.
        last_rotated_at: Last rotation timestamp.
        next_rotation_at: Next scheduled rotation.
        access_count: Number of times secret was read.
        namespace: Namespace for isolation.
    """

    key: str
    provider: str = "local"
    version: int = 1
    status: SecretStatus = SecretStatus.ACTIVE
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_rotated_at: Optional[datetime] = None
    next_rotation_at: Optional[datetime] = None
    access_count: int = 0
    namespace: str = "default"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "key": self.key,
            "provider": self.provider,
            "version": self.version,
            "status": self.status.value,
            "created_at": self.created_at.isoformat() + "Z",
            "last_rotated_at": (
                self.last_rotated_at.isoformat() + "Z"
                if self.last_rotated_at
                else None
            ),
            "next_rotation_at": (
                self.next_rotation_at.isoformat() + "Z"
                if self.next_rotation_at
                else None
            ),
            "access_count": self.access_count,
            "namespace": self.namespace,
        }


@dataclass
class SecretChangeEntry:
    """
    Record of a secret change.

    Captures details about a single
    secret modification for audit
    and history tracking.

    Attributes:
        key: The secret key.
        action: Action performed (create, update, delete, rotate).
        old_version: Previous version number.
        new_version: New version number.
        operator: Who performed the action.
        reason: Reason for the change.
        timestamp: When the change occurred.
        trace_id: Trace ID for correlation.
        metadata: Additional context.
    """

    key: str
    action: str
    old_version: Optional[int] = None
    new_version: Optional[int] = None
    operator: str = "system"
    reason: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    trace_id: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "key": self.key,
            "action": self.action,
            "old_version": self.old_version,
            "new_version": self.new_version,
            "operator": self.operator,
            "reason": self.reason,
            "timestamp": self.timestamp.isoformat() + "Z",
            "trace_id": self.trace_id,
            "metadata": self.metadata,
        }


@dataclass
class SecretAccessEntry:
    """
    Record of a secret access.

    Captures details about a single
    secret read operation for audit
    and analytics.

    Attributes:
        key: The secret key.
        operator: Who accessed the secret.
        allowed: Whether access was allowed.
        source: Access source (service, strategy, etc.).
        timestamp: When the access occurred.
        trace_id: Trace ID for correlation.
        cache_hit: Whether the value was cached.
        latency_ms: Access latency in milliseconds.
    """

    key: str
    operator: str = "system"
    allowed: bool = True
    source: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    trace_id: str = ""
    cache_hit: bool = False
    latency_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "key": self.key,
            "operator": self.operator,
            "allowed": self.allowed,
            "source": self.source,
            "timestamp": self.timestamp.isoformat() + "Z",
            "trace_id": self.trace_id,
            "cache_hit": self.cache_hit,
            "latency_ms": self.latency_ms,
        }


@dataclass
class ValidationIssue:
    """
    A single validation issue.

    Attributes:
        field: The field name with the issue.
        message: Human-readable description.
        severity: Issue severity level.
        code: Machine-readable error code.
    """

    field: str
    message: str
    severity: str = "warning"
    code: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "field": self.field,
            "message": self.message,
            "severity": self.severity,
            "code": self.code,
        }


@dataclass
class ValidationResult:
    """
    Result of a secret validation.

    Attributes:
        valid: Overall validity flag.
        issues: List of validation issues.
        timestamp: When validation was performed.
    """

    valid: bool = True
    issues: List[ValidationIssue] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "valid": self.valid,
            "issues": [issue.to_dict() for issue in self.issues],
            "timestamp": self.timestamp.isoformat() + "Z",
        }
