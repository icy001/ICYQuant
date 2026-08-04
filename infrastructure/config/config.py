"""
Configuration platform configuration.

Defines the configuration for the configuration
platform itself (meta-configuration), controlling
how the platform behaves.

Attributes:
    enabled: Whether the configuration platform is active.
    cache_enabled: Whether to use caching.
    validation_enabled: Whether to validate configs.
    auto_reload: Whether to auto-reload on file changes.
    environment: Deployment environment.
    default_loader: Default loader type (yaml/json/toml/env).
    cache_ttl: Cache time-to-live in seconds.
    cache_max_size: Maximum number of cached items.
    reload_interval: Auto-reload check interval in seconds.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from .constants import (
    DEFAULT_CACHE_TTL,
    DEFAULT_CACHE_MAX_SIZE,
    DEFAULT_ENVIRONMENT,
    DEFAULT_LOADER,
    DEFAULT_RELOAD_INTERVAL,
    DEFAULT_VALIDATION_LEVEL,
    ValidationLevel,
)


class ConfigurationPlatformConfig(BaseModel):
    """
    Configuration platform configuration.

    Controls the behavior of the configuration
    platform itself, including caching, validation,
    auto-reload, and default settings.

    Usage:
        config = ConfigurationPlatformConfig(
            environment="production",
            cache_enabled=True,
            auto_reload=True,
        )
    """

    enabled: bool = True
    cache_enabled: bool = True
    validation_enabled: bool = True
    auto_reload: bool = False
    environment: str = DEFAULT_ENVIRONMENT
    default_loader: str = DEFAULT_LOADER
    cache_ttl: int = Field(
        default=DEFAULT_CACHE_TTL,
        ge=0,
        description="Cache TTL in seconds",
    )
    cache_max_size: int = Field(
        default=DEFAULT_CACHE_MAX_SIZE,
        ge=1,
        description="Maximum cache entries",
    )
    reload_interval: float = Field(
        default=DEFAULT_RELOAD_INTERVAL,
        gt=0,
        description="Auto-reload check interval in seconds",
    )
    validation_level: str = Field(
        default=DEFAULT_VALIDATION_LEVEL,
        description="Validation strictness level",
    )
    config_dir: Optional[str] = Field(
        default=None,
        description="Default configuration directory",
    )
    config_file: Optional[str] = Field(
        default=None,
        description="Default configuration file",
    )

    model_config = {
        "use_enum_values": True,
        "validate_assignment": True,
    }

    def is_production(
        self,
    ) -> bool:
        """Check if running in production."""

        return self.environment == "production"

    def is_development(
        self,
    ) -> bool:
        """Check if running in development."""

        return self.environment == "development"

    def is_strict_validation(
        self,
    ) -> bool:
        """Check if strict validation is enabled."""

        return self.validation_level == ValidationLevel.STRICT.value
