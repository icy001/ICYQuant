"""
Secrets platform configuration.

Defines the Pydantic configuration model
for the secrets management platform,
including provider selection, caching,
encryption, and audit settings.
"""

from __future__ import annotations

from typing import List, Optional

try:
    from pydantic import BaseModel, Field
except ImportError:
    from pydantic import BaseModel, Field


class SecretsConfig(BaseModel):
    """
    Secrets platform configuration.

    Controls platform-wide settings including
    provider selection, cache behavior, encryption
    requirements, and audit logging.

    Usage:
        config = SecretsConfig()
        config = SecretsConfig(provider="aws_secrets_manager")
    """

    model_config = {"extra": "allow"}

    enabled: bool = Field(
        default=True,
        description="Enable the secrets platform",
    )
    cache_enabled: bool = Field(
        default=True,
        description="Enable secret value caching",
    )
    cache_ttl: int = Field(
        default=300,
        ge=0,
        description="Cache TTL in seconds (0 = disabled)",
    )
    cache_max_size: int = Field(
        default=1000,
        ge=1,
        description="Maximum number of cached secrets",
    )
    provider: str = Field(
        default="local",
        description="Primary secrets provider name",
    )
    encryption_required: bool = Field(
        default=True,
        description="Require encryption for secrets at rest",
    )
    audit_enabled: bool = Field(
        default=True,
        description="Enable audit logging for all secret access",
    )
    audit_log_path: Optional[str] = Field(
        default=None,
        description="Path for audit log storage",
    )
    default_namespace: str = Field(
        default="default",
        description="Default secrets namespace",
    )
    rotation_enabled: bool = Field(
        default=True,
        description="Enable automatic key rotation",
    )
    rotation_interval_days: int = Field(
        default=90,
        ge=1,
        description="Default rotation interval in days",
    )
    max_secret_size: int = Field(
        default=65536,
        ge=1,
        description="Maximum secret value size in bytes",
    )
    allowed_providers: List[str] = Field(
        default=[
            "local",
            "vault",
            "aws_secrets_manager",
            "azure_key_vault",
            "google_secret_manager",
        ],
        description="Allowed provider names",
    )
    rate_limit_per_minute: int = Field(
        default=100,
        ge=1,
        description="Max secret reads per minute",
    )
    connection_timeout: float = Field(
        default=30.0,
        ge=1.0,
        description="Provider connection timeout in seconds",
    )
    read_timeout: float = Field(
        default=10.0,
        ge=1.0,
        description="Provider read operation timeout in seconds",
    )

    def to_dict(self) -> dict:
        """Convert config to dictionary."""
        return self.model_dump()
