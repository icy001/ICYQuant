"""
Rollout policy models.

Defines the data structures for configuring
percentage-based rollout policies including
percentage, hash key dimension, and enabled state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class RolloutPolicy:
    """
    Configuration for a percentage-based rollout.

    Controls how a feature flag is gradually
    deployed to a subset of targets based on
    consistent hashing.

    Attributes:
        percentage: Rollout percentage (0-100).
        hash_key: Attribute to hash on (account_id, user_id, etc).
        enabled: Whether the rollout is active.
        algorithm: Hash algorithm (murmur3, sha256, crc32).
        max_buckets: Total buckets for hash distribution.
        sticky: Whether to use sticky assignment.
        description: Human-readable description.
        metadata: Additional key-value metadata.
    """

    percentage: float = 0.0
    hash_key: str = "account_id"
    enabled: bool = True
    algorithm: str = "murmur3"
    max_buckets: int = 10000
    sticky: bool = True
    description: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate policy after initialization."""
        if self.percentage < 0 or self.percentage > 100:
            raise ValueError(
                f"Percentage must be between 0 and 100, got: {self.percentage}",
            )
        if self.max_buckets < 100:
            raise ValueError(
                f"max_buckets must be >= 100, got: {self.max_buckets}",
            )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the policy to a dictionary."""
        return {
            "percentage": self.percentage,
            "hash_key": self.hash_key,
            "enabled": self.enabled,
            "algorithm": self.algorithm,
            "max_buckets": self.max_buckets,
            "sticky": self.sticky,
            "description": self.description,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RolloutPolicy":
        """Create a policy from a dictionary."""
        return cls(
            percentage=data.get("percentage", 0.0),
            hash_key=data.get("hash_key", "account_id"),
            enabled=data.get("enabled", True),
            algorithm=data.get("algorithm", "murmur3"),
            max_buckets=data.get("max_buckets", 10000),
            sticky=data.get("sticky", True),
            description=data.get("description", ""),
            metadata=data.get("metadata", {}),
        )


@dataclass
class RolloutAssignment:
    """
    Result of a rollout assignment decision.

    Records the full decision trace for audit
    and debugging purposes.

    Attributes:
        flag_key: Feature flag key.
        target_id: Target identifier.
        hash_value: Computed hash value.
        bucket: Assigned bucket.
        percentage: Current rollout percentage.
        assigned: Whether the target is assigned to the rollout.
        hash_key: Hash key dimension used.
        algorithm: Hash algorithm used.
        sticky: Whether sticky assignment was applied.
        duration_ms: Decision duration in milliseconds.
        timestamp: When the decision was made.
        version: Rollout version for tracking.
    """

    flag_key: str = ""
    target_id: str = ""
    hash_value: int = 0
    bucket: int = 0
    percentage: float = 0.0
    assigned: bool = False
    hash_key: str = ""
    algorithm: str = ""
    sticky: bool = True
    duration_ms: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)
    version: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the assignment to a dictionary."""
        return {
            "flag_key": self.flag_key,
            "target_id": self.target_id,
            "hash_value": self.hash_value,
            "bucket": self.bucket,
            "percentage": self.percentage,
            "assigned": self.assigned,
            "hash_key": self.hash_key,
            "algorithm": self.algorithm,
            "sticky": self.sticky,
            "duration_ms": self.duration_ms,
            "timestamp": self.timestamp.isoformat(),
            "version": self.version,
        }


@dataclass
class ProgressiveStage:
    """
    A single stage in a progressive rollout plan.

    Defines a target percentage and the conditions
    for advancing to this stage.

    Attributes:
        stage_id: Unique stage identifier.
        percentage: Target percentage for this stage.
        delay_seconds: Delay before advancing (0 = immediate).
        auto_advance: Whether to auto-advance on health check pass.
        min_requests: Minimum requests before auto-advance.
        error_threshold: Error rate threshold for blocking advance.
        description: Human-readable description.
    """

    stage_id: str = ""
    percentage: float = 0.0
    delay_seconds: float = 0.0
    auto_advance: bool = True
    min_requests: int = 100
    error_threshold: float = 5.0
    description: str = ""

    def __post_init__(self) -> None:
        """Validate stage after initialization."""
        if self.percentage < 0 or self.percentage > 100:
            raise ValueError(
                f"Stage percentage must be between 0 and 100, "
                f"got: {self.percentage}",
            )
        if self.error_threshold < 0 or self.error_threshold > 100:
            raise ValueError(
                f"Error threshold must be between 0 and 100, "
                f"got: {self.error_threshold}",
            )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the stage to a dictionary."""
        return {
            "stage_id": self.stage_id,
            "percentage": self.percentage,
            "delay_seconds": self.delay_seconds,
            "auto_advance": self.auto_advance,
            "min_requests": self.min_requests,
            "error_threshold": self.error_threshold,
            "description": self.description,
        }


@dataclass
class SegmentDefinition:
    """
    A segment definition for segment-based rollout.

    Segments allow targeting specific groups of
    targets based on attribute matching.

    Attributes:
        segment_id: Unique segment identifier.
        name: Segment name.
        attribute: Attribute to match on.
        operator: Comparison operator (==, IN, etc).
        values: Values to match against.
        percentage: Override percentage for this segment.
        enabled: Whether the segment is active.
        priority: Evaluation priority (lower = first).
        description: Human-readable description.
    """

    segment_id: str = ""
    name: str = ""
    attribute: str = ""
    operator: str = "=="
    values: List[Any] = field(default_factory=list)
    percentage: Optional[float] = None
    enabled: bool = True
    priority: int = 0
    description: str = ""

    def __post_init__(self) -> None:
        """Validate segment after initialization."""
        valid_ops = ("==", "!=", "IN", "NOT IN", "CONTAINS")
        if self.operator not in valid_ops:
            raise ValueError(
                f"Invalid operator: {self.operator}. "
                f"Valid: {', '.join(valid_ops)}",
            )

    def matches(self, attributes: Dict[str, Any]) -> bool:
        """
        Check if a set of attributes matches this segment.

        Args:
            attributes: Attribute dictionary.

        Returns:
            True if attributes match the segment definition.
        """
        actual = attributes.get(self.attribute)
        if actual is None:
            return False

        if self.operator == "==":
            return str(actual).lower() == str(self.values[0]).lower()

        elif self.operator == "!=":
            return str(actual).lower() != str(self.values[0]).lower()

        elif self.operator == "IN":
            return str(actual).lower() in [str(v).lower() for v in self.values]

        elif self.operator == "NOT IN":
            return str(actual).lower() not in [str(v).lower() for v in self.values]

        elif self.operator == "CONTAINS":
            return str(self.values[0]).lower() in str(actual).lower()

        return False

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the segment to a dictionary."""
        return {
            "segment_id": self.segment_id,
            "name": self.name,
            "attribute": self.attribute,
            "operator": self.operator,
            "values": self.values,
            "percentage": self.percentage,
            "enabled": self.enabled,
            "priority": self.priority,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SegmentDefinition":
        """Create a segment from a dictionary."""
        return cls(
            segment_id=data.get("segment_id", ""),
            name=data.get("name", ""),
            attribute=data.get("attribute", ""),
            operator=data.get("operator", "=="),
            values=data.get("values", []),
            percentage=data.get("percentage"),
            enabled=data.get("enabled", True),
            priority=data.get("priority", 0),
            description=data.get("description", ""),
        )
