"""Configuration Adapter — integrates the Scheduler with the Configuration Center.

The :class:`ConfigurationAdapter` enables dynamic configuration management:
* Hot reload of scheduler configs without restart
* Policy updates for triggers, resources, and scheduling
* Configuration versioning and rollback
* Environment-specific config overlays

Architecture::

    Configuration Center ──→ ConfigurationAdapter ──→ SchedulerEngine
                                 │
                          Hot Reload / Policy Update
"""

from __future__ import annotations

import asyncio
import enum
import logging
import threading
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class ConfigSource(enum.Enum):
    """Configuration source types."""

    FILE = "file"
    CONSUL = "consul"
    ETCD = "etcd"
    DATABASE = "database"
    ENVIRONMENT = "environment"


class ConfigurationAdapter:
    """Adapter for dynamic configuration management.

    Responsibilities:
    * Load configuration from the configuration center
    * Watch for configuration changes (hot reload)
    * Apply configuration updates without restart
    * Validate configuration schemas
    * Version configuration changes

    Usage::

        adapter = ConfigurationAdapter(source=ConfigSource.CONSUL)
        await adapter.connect()
        config = await adapter.load("scheduler.policy")
        await adapter.watch("scheduler.policy", on_config_changed)
    """

    def __init__(self, source: ConfigSource = ConfigSource.FILE) -> None:
        self._source = source
        self._lock = threading.Lock()
        self._connected = False
        self._configs: Dict[str, Any] = {}
        self._watchers: Dict[str, List[Callable]] = {}
        self._versions: Dict[str, int] = {}
        self._load_count: int = 0
        self._update_count: int = 0
        self._last_load_at: Optional[datetime] = None
        self._defaults: Dict[str, Any] = {}

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def source(self) -> ConfigSource:
        return self._source

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def load_count(self) -> int:
        return self._load_count

    @property
    def update_count(self) -> int:
        return self._update_count

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def connect(self) -> None:
        """Connect to the configuration center."""
        logger.info("ConfigurationAdapter: connecting to %s", self._source.value)
        self._connected = True

    async def disconnect(self) -> None:
        """Disconnect from the configuration center."""
        self._connected = False
        self._watchers.clear()
        logger.info("ConfigurationAdapter: disconnected")

    async def synchronize(self) -> Dict[str, Any]:
        """Synchronize configurations."""
        return {
            "source": self._source.value,
            "configs_loaded": len(self._configs),
            "watchers": len(self._watchers),
        }

    # ------------------------------------------------------------------
    # Load & Reload
    # ------------------------------------------------------------------

    async def load(self, key: str, default: Any = None) -> Any:
        """Load a configuration value by key.

        Falls back to registered defaults if the key is not found.
        """
        self._load_count += 1
        self._last_load_at = datetime.now(timezone.utc)

        if key in self._configs:
            return self._configs[key]

        # Try defaults
        if key in self._defaults:
            self._configs[key] = self._defaults[key]
            return self._defaults[key]

        return default

    async def load_all(self, prefix: str = "") -> Dict[str, Any]:
        """Load all configuration values under a prefix."""
        if not prefix:
            return dict(self._configs)
        return {k: v for k, v in self._configs.items() if k.startswith(prefix)}

    async def reload(self, key: str) -> Any:
        """Force reload a configuration value from source."""
        # In real impl, this queries the config center
        self._load_count += 1
        return self._configs.get(key)

    # ------------------------------------------------------------------
    # Hot Reload (Watch)
    # ------------------------------------------------------------------

    async def watch(self, key: str, callback: Callable) -> None:
        """Watch a configuration key for changes (hot reload).

        The callback is invoked whenever the configuration changes.
        """
        if key not in self._watchers:
            self._watchers[key] = []
        self._watchers[key].append(callback)
        logger.info("ConfigurationAdapter: watching %s", key)

    async def unwatch(self, key: str, callback: Optional[Callable] = None) -> None:
        """Stop watching a configuration key."""
        if key not in self._watchers:
            return
        if callback:
            self._watchers[key].remove(callback)
            if not self._watchers[key]:
                del self._watchers[key]
        else:
            del self._watchers[key]

    async def notify_change(self, key: str, value: Any) -> None:
        """Notify watchers of a configuration change (hot reload)."""
        old_value = self._configs.get(key)
        self._configs[key] = value
        self._versions[key] = self._versions.get(key, 0) + 1
        self._update_count += 1

        logger.info("ConfigurationAdapter: %s changed (v%d)", key, self._versions[key])

        # Notify watchers
        for callback in self._watchers.get(key, []):
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(key, value, old_value)
                else:
                    callback(key, value, old_value)
            except Exception as exc:
                logger.warning("ConfigurationAdapter: watcher error for %s: %s", key, exc)

    # ------------------------------------------------------------------
    # Defaults
    # ------------------------------------------------------------------

    def set_default(self, key: str, value: Any) -> None:
        """Set a default value for a configuration key."""
        self._defaults[key] = value

    def set_defaults(self, defaults: Dict[str, Any]) -> None:
        """Set multiple default configuration values."""
        self._defaults.update(defaults)

    # ------------------------------------------------------------------
    # Versioning
    # ------------------------------------------------------------------

    def get_version(self, key: str) -> int:
        """Get the current version of a configuration key."""
        return self._versions.get(key, 0)

    async def rollback(self, key: str, version: int) -> bool:
        """Rollback a configuration to a previous version."""
        logger.warning("ConfigurationAdapter: rollback %s to v%d (not implemented)", key, version)
        return False
