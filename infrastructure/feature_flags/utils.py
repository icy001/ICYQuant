"""
Feature flag platform utility functions.

Provides helper functions for hashing,
key generation, serialization, and
consistent hashing for percentage rollouts.
"""

from __future__ import annotations

import hashlib
import json
import struct
import uuid
from datetime import datetime
from typing import Any, Dict, Optional


def generate_id() -> str:
    """Generate a unique identifier."""
    return uuid.uuid4().hex[:12]


def generate_trace_id() -> str:
    """Generate a trace ID for audit correlation."""
    return uuid.uuid4().hex


def compute_checksum(data: Any) -> str:
    """
    Compute a SHA-256 checksum for any serializable data.

    Args:
        data: Data to hash.

    Returns:
        Hex-encoded SHA-256 checksum.
    """
    serialized = json.dumps(data, default=str, sort_keys=True)
    return hashlib.sha256(serialized.encode()).hexdigest()


def consistent_hash(
    key: str,
    max_value: int = 10000,
) -> int:
    """
    Compute a consistent hash for percentage-based rollouts.

    Uses MD5 hash to ensure the same key always maps to
    the same bucket, preventing rollout churn on restart.

    Args:
        key: Key to hash (e.g. account ID + flag key).
        max_value: Maximum bucket value (exclusive).

    Returns:
        Stable hash value in range [0, max_value).
    """
    digest = hashlib.md5(key.encode()).digest()
    (value,) = struct.unpack("<I", digest[:4])
    return value % max_value


def is_in_rollout(
    flag_key: str,
    target_id: str,
    percentage: float,
) -> bool:
    """
    Determine if a target falls within a percentage rollout.

    Uses consistent hashing to ensure the same target
    always gets the same result for a given flag key.

    Args:
        flag_key: Feature flag key.
        target_id: Target identifier (account, user, etc).
        percentage: Rollout percentage (0.0 - 100.0).

    Returns:
        True if the target is in the rollout.
    """
    combined = f"{flag_key}:{target_id}"
    bucket = consistent_hash(combined)
    return bucket < int(percentage * 100)


def serialize_flag(flag: Any) -> Dict[str, Any]:
    """
    Serialize a feature flag to a dictionary.

    Handles dataclasses and Pydantic models.

    Args:
        flag: Feature flag object.

    Returns:
        Dictionary representation.
    """
    if hasattr(flag, "model_dump"):
        return flag.model_dump()
    elif hasattr(flag, "__dataclass_fields__"):
        from dataclasses import asdict
        return asdict(flag)
    return {}


def format_timestamp(dt: Optional[datetime] = None) -> str:
    """Format a datetime to ISO 8601 UTC string."""
    if dt is None:
        dt = datetime.utcnow()
    return dt.isoformat() + "Z"


def parse_timestamp(s: str) -> datetime:
    """Parse an ISO 8601 timestamp string."""
    s = s.replace("Z", "+00:00")
    return datetime.fromisoformat(s)


def sanitize_flag_key(key: str) -> str:
    """
    Sanitize a feature flag key.

    Ensures the key follows the allowed pattern:
    lowercase alphanumeric, dots, hyphens, underscores.

    Args:
        key: Raw flag key.

    Returns:
        Sanitized key.

    Raises:
        ValueError: If the key contains invalid characters.
    """
    import re

    key = key.strip().lower()
    if not re.match(r"^[a-z][a-z0-9._-]*$", key):
        raise ValueError(
            f"Invalid feature flag key: {key}. "
            "Must start with a letter and contain only "
            "lowercase letters, digits, dots, hyphens, underscores.",
        )
    return key


def compact_dict(data: Dict[str, Any]) -> Dict[str, Any]:
    """Remove None values from a dictionary."""
    return {k: v for k, v in data.items() if v is not None}


def deep_merge(
    base: Dict[str, Any],
    override: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Deep merge two dictionaries.

    Override values take precedence. Nested dicts
    are merged recursively.

    Args:
        base: Base dictionary.
        override: Override dictionary.

    Returns:
        Merged dictionary.
    """
    result = dict(base)
    for key, value in override.items():
        if (
            key in result
            and isinstance(result[key], dict)
            and isinstance(value, dict)
        ):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def clamp(
    value: float,
    min_val: float,
    max_val: float,
) -> float:
    """Clamp a value between min and max."""
    return max(min_val, min(max_val, value))