"""
Feature flag platform configuration.

Defines the configuration for the feature flag
platform, controlling cache behavior, audit,
metrics, and storage backends.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from .constants import (
    DEFAULT_CACHE_MAX_SIZE,
    DEFAULT_CACHE_TTL,
    DEFAULT_EVAL_TIMEOUT_SECONDS,
    DEFAULT_MAX_RULES_PER_FLAG,
    DEFAULT_STORAGE_BACKEND,
    StorageBackend,
)


class FeatureFlagConfig(BaseModel):
    """
    Feature flag platform configuration.

    Controls the behavior of the feature flag
    platform including caching, auditing,
    metrics collection, and storage backend.

    Usage:
        config = FeatureFlagConfig(
            cache_enabled=True,
            cache_ttl=30,
            storage_backend="redis",
        )
    """

    enabled: bool = Field(
        default=True,
        description="Whether the feature flag platform is active.",
    )

    cache_enabled: bool = Field(
        default=True,
        description="Whether to enable local caching for evaluations.",
    )

    cache_ttl: int = Field(
        default=DEFAULT_CACHE_TTL,
        ge=1,
        le=3600,
        description="Cache time-to-live in seconds.",
    )

    cache_max_size: int = Field(
        default=DEFAULT_CACHE_MAX_SIZE,
        ge=1,
        le=65536,
        description="Maximum number of entries in the local cache.",
    )

    audit_enabled: bool = Field(
        default=True,
        description="Whether to record audit logs for flag changes.",
    )

    audit_max_entries: int = Field(
        default=10000,
        ge=1,
        description="Maximum audit entries to retain in memory.",
    )

    metrics_enabled: bool = Field(
        default=True,
        description="Whether to collect and expose Prometheus metrics.",
    )

    health_check_enabled: bool = Field(
        default=True,
        description="Whether to run periodic health checks.",
    )

    storage_backend: StorageBackend = Field(
        default=DEFAULT_STORAGE_BACKEND,
        description="Storage backend type for flag definitions.",
    )

    storage_config: Optional[dict] = Field(
        default=None,
        description="Backend-specific storage configuration.",
    )

    eval_timeout_seconds: float = Field(
        default=DEFAULT_EVAL_TIMEOUT_SECONDS,
        ge=0.1,
        le=60.0,
        description="Timeout for flag evaluation in seconds.",
    )

    max_rules_per_flag: int = Field(
        default=DEFAULT_MAX_RULES_PER_FLAG,
        ge=1,
        le=1000,
        description="Maximum targeting rules per flag.",
    )

    @classmethod
    def default(cls) -> "FeatureFlagConfig":
        """Create a default configuration."""
        return cls()