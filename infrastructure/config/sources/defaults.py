"""
Default Values Configuration Source.

Provides default configuration values.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from .base import ConfigurationSource
from ..priority import ConfigurationPriority


class DefaultsSource(ConfigurationSource):
    """
    Provides default configuration values.

    This is the lowest priority source and
    should contain sensible defaults that
    can be overridden by higher priority sources.
    """

    name = "defaults"
    priority = ConfigurationPriority.DEFAULT

    def __init__(
        self,
        defaults: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Initialize defaults source.

        Args:
            defaults: Dictionary of default values.
        """
        self._defaults = defaults or self._get_defaults()

    def load(self) -> Dict[str, Any]:
        """Load default configuration values."""
        return dict(self._defaults)

    def _get_defaults(self) -> Dict[str, Any]:
        """Get default configuration values."""
        return {
            # Server
            "server.host": "0.0.0.0",
            "server.port": 8080,
            "server.debug": False,
            # Database
            "database.host": "localhost",
            "database.port": 5432,
            "database.name": "icyquant",
            "database.pool_size": 10,
            # Redis
            "redis.host": "localhost",
            "redis.port": 6379,
            "redis.db": 0,
            # Kafka
            "kafka.bootstrap_servers": "localhost:9092",
            "kafka.group_id": "icyquant",
            # Application
            "app.name": "ICYQuant",
            "app.version": "0.0.0",
            "app.environment": "development",
            # Logging
            "logging.level": "INFO",
            "logging.file": None,
        }
