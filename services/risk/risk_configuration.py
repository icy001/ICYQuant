"""
Risk Configuration — Centralized risk platform configuration management.

Manages risk engine configuration, policy settings, runtime parameters,
and environment-specific risk tuning.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class RiskConfiguration:
    """Comprehensive risk platform configuration."""
    platform_id: str = "icyquant-risk"

    # Engine settings
    max_concurrent_evaluations: int = 50
    evaluation_timeout_seconds: float = 10.0
    default_decision_timeout_seconds: float = 5.0

    # Policy defaults
    default_policy_severity: str = "blocking"
    auto_enable_new_policies: bool = True
    policy_cache_ttl_seconds: float = 60.0

    # Runtime settings
    heartbeat_interval_seconds: float = 5.0
    snapshot_interval_minutes: int = 15
    max_evaluation_history: int = 10000

    # Recovery settings
    enable_auto_recovery: bool = True
    max_recovery_attempts: int = 3
    recovery_backoff_seconds: float = 5.0

    # Audit settings
    enable_audit_logging: bool = True
    audit_retention_days: int = 365

    # Environment overrides
    environment: str = "production"
    metadata: dict[str, Any] = field(default_factory=dict)
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class RiskConfigManager:
    """
    Centralized risk platform configuration management.

    Manages all risk engine settings with environment-specific
    overrides and runtime configuration hot-reload.

    Usage::

        mgr = RiskConfigManager()
        await mgr.initialize()
        config = mgr.get_configuration()
        await mgr.update(max_concurrent_evaluations=100)
    """

    def __init__(self, config: Optional[RiskConfiguration] = None) -> None:
        self._config = config or RiskConfiguration()
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        """Initialize the configuration manager."""
        logger.info(f"RiskConfigManager initialized (env: {self._config.environment})")

    async def stop(self) -> None:
        """Stop the configuration manager."""
        logger.info("RiskConfigManager stopped.")

    def get_configuration(self) -> RiskConfiguration:
        """Get the current configuration."""
        return self._config

    async def update(self, **kwargs: Any) -> RiskConfiguration:
        """Update configuration parameters."""
        async with self._lock:
            for key, value in kwargs.items():
                if hasattr(self._config, key):
                    old = getattr(self._config, key)
                    setattr(self._config, key, value)
                    logger.info(f"Config updated: {key} = {value} (was {old})")
                else:
                    self._config.metadata[key] = value
            self._config.updated_at = datetime.now(timezone.utc)
        return self._config

    async def reset(self) -> RiskConfiguration:
        """Reset to default configuration."""
        self._config = RiskConfiguration()
        logger.info("Configuration reset to defaults.")
        return self._config

    async def export(self) -> dict[str, Any]:
        """Export configuration as dictionary."""
        return {
            "platform_id": self._config.platform_id,
            "max_concurrent_evaluations": self._config.max_concurrent_evaluations,
            "evaluation_timeout_seconds": self._config.evaluation_timeout_seconds,
            "default_decision_timeout_seconds": self._config.default_decision_timeout_seconds,
            "default_policy_severity": self._config.default_policy_severity,
            "auto_enable_new_policies": self._config.auto_enable_new_policies,
            "heartbeat_interval_seconds": self._config.heartbeat_interval_seconds,
            "snapshot_interval_minutes": self._config.snapshot_interval_minutes,
            "enable_auto_recovery": self._config.enable_auto_recovery,
            "enable_audit_logging": self._config.enable_audit_logging,
            "environment": self._config.environment,
            "metadata": self._config.metadata,
        }

    async def health_check(self) -> dict[str, Any]:
        """Check configuration health."""
        return {
            "status": "healthy",
            "environment": self._config.environment,
        }
