"""
Configuration manager.

The unified entry point for the configuration
platform, coordinating the registry, cache,
validator, and loader components.

Runtime Flow:

    Application
          |
          v
    ConfigurationManager
          |
          +-------> Registry (immutable snapshots)
          |
          +-------> Cache (fast access)
          |
          +-------> Validator (validation)
          |
          +-------> Loader (multi-source)

Usage:
    manager = ConfigurationManager()
    manager.set("server.port", 8080)
    manager.set("server.host", "0.0.0.0")

    # Get values (thread-safe, from immutable snapshot)
    port = manager.get("server.port")  # 8080
    port = manager.get_typed("server.port", int)  # 8080

    # Get entire snapshot
    snapshot = manager.get_snapshot()

    # Load from file
    manager.load_from_file("config.yaml")

    # Validate
    result = manager.validate()
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Type

from .cache import ConfigurationCache
from .config import ConfigurationPlatformConfig
from .constants import ConfigSource, DEFAULT_ENVIRONMENT
from .exceptions import ConfigNotFoundError, ConfigValidationError
from .loader import ConfigurationLoader, LoaderFactory, MultiSourceLoader
from .models import ConfigurationItem, ConfigurationSnapshot, ValidationResult
from .registry import ConfigurationRegistry
from .validator import ConfigurationValidator


class ConfigurationManager:
    """
    Configuration manager.

    Coordinates all configuration platform
    components, providing a single entry point
    for configuration access, loading, and
    validation.

    Features:
    - Thread-safe configuration access
    - Immutable snapshot reads
    - Multi-source loading with priority
    - Configuration validation
    - TTL-based caching
    - Rollback support
    - Change notification (future)

    Usage:
        manager = ConfigurationManager()
        manager.set("server.port", 8080)

        # Thread-safe read (from immutable snapshot)
        port = manager.get("server.port")

        # Typed read
        host = manager.get_typed("server.host", str)

        # Load from file
        manager.load_from_file("config.yaml")

        # Validate
        result = manager.validate()
    """

    def __init__(
        self,
        config: Optional[ConfigurationPlatformConfig] = None,
        registry: Optional[ConfigurationRegistry] = None,
        cache: Optional[ConfigurationCache] = None,
        validator: Optional[ConfigurationValidator] = None,
    ) -> None:
        """
        Initialize configuration manager.

        Args:
            config: Platform configuration.
            registry: Pre-configured registry.
            cache: Pre-configured cache.
            validator: Pre-configured validator.
        """

        self._config = config or ConfigurationPlatformConfig()
        self._registry = registry or ConfigurationRegistry(
            environment=self._config.environment,
        )
        self._cache = cache or ConfigurationCache(
            ttl=self._config.cache_ttl,
            max_size=self._config.cache_max_size,
        )
        self._validator = validator or ConfigurationValidator()
        self._multi_loader = MultiSourceLoader()

    # ── Properties ──

    @property
    def config(
        self,
    ) -> ConfigurationPlatformConfig:
        """Get platform config."""
        return self._config

    @property
    def registry(
        self,
    ) -> ConfigurationRegistry:
        """Get registry."""
        return self._registry

    @property
    def cache(
        self,
    ) -> ConfigurationCache:
        """Get cache."""
        return self._cache

    @property
    def validator(
        self,
    ) -> ConfigurationValidator:
        """Get validator."""
        return self._validator

    @property
    def multi_loader(
        self,
    ) -> MultiSourceLoader:
        """Get multi-source loader."""
        return self._multi_loader

    @property
    def environment(
        self,
    ) -> str:
        """Get environment."""
        return self._registry.environment

    @property
    def snapshot_version(
        self,
    ) -> int:
        """Get current snapshot version."""
        return self._registry.snapshot_version

    @property
    def item_count(
        self,
    ) -> int:
        """Get number of config items."""
        return self._registry.item_count

    # ── Core Operations ──

    def get(
        self,
        key: str,
        default: Any = None,
        use_cache: bool = True,
    ) -> Any:
        """
        Get a configuration value.

        Reads from cache if available (and caching
        is enabled), otherwise reads from the
        immutable registry snapshot.

        Args:
            key: Configuration key.
            default: Default value if not found.
            use_cache: Whether to check cache.

        Returns:
            Configuration value.
        """

        # Check cache first
        if use_cache and self._config.cache_enabled:
            cached = self._cache.get(key)
            if cached is not None:
                return cached

        # Read from registry snapshot
        value = self._registry.get(key, default)

        # Cache the value
        if (
            use_cache
            and self._config.cache_enabled
            and value is not None
        ):
            self._cache.put(key, value)

        return value

    def get_typed(
        self,
        key: str,
        value_type: Type,
        default: Any = None,
    ) -> Any:
        """
        Get a typed configuration value.

        Args:
            key: Configuration key.
            value_type: Expected type (int, str, bool, etc.).
            default: Default value if not found or type mismatch.

        Returns:
            Typed configuration value.
        """

        return self._registry.get_typed(key, value_type, default)

    def get_item(
        self,
        key: str,
    ) -> Optional[ConfigurationItem]:
        """Get a configuration item with metadata."""
        return self._registry.get_item(key)

    def get_snapshot(
        self,
    ) -> ConfigurationSnapshot:
        """Get the current immutable snapshot."""
        return self._registry.get_snapshot()

    def set(
        self,
        key: str,
        value: Any,
        source: str = ConfigSource.FILE.value,
        readonly: bool = False,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Set a configuration value.

        Updates the registry, which creates a new
        immutable snapshot atomically. Also
        invalidates the cache for this key.

        Args:
            key: Configuration key.
            value: Configuration value.
            source: Value source.
            readonly: Whether value is read-only.
            metadata: Additional metadata.
        """

        self._registry.set(
            key=key,
            value=value,
            source=source,
            readonly=readonly,
            metadata=metadata,
        )

        # Invalidate cache for this key
        self._cache.delete(key)

    def set_many(
        self,
        items: Dict[str, Any],
        source: str = ConfigSource.FILE.value,
    ) -> None:
        """Set multiple configuration values at once."""

        self._registry.set_many(items, source=source)

        # Invalidate cache for all keys
        for key in items:
            self._cache.delete(key)

    def delete(
        self,
        key: str,
    ) -> bool:
        """Delete a configuration item."""

        result = self._registry.delete(key)
        if result:
            self._cache.delete(key)
        return result

    def exists(
        self,
        key: str,
    ) -> bool:
        """Check if a key exists."""
        return self._registry.exists(key)

    def keys(
        self,
    ) -> List[str]:
        """Get all configuration keys."""
        return self._registry.keys()

    # ── Loading ──

    def load_from_file(
        self,
        path: str,
        loader_type: Optional[str] = None,
    ) -> ConfigurationSnapshot:
        """
        Load configuration from a file.

        Args:
            path: File path.
            loader_type: Loader type (auto-detected if None).

        Returns:
            Loaded ConfigurationSnapshot.
        """

        if loader_type is None:
            loader_type = self._detect_loader_type(path)

        loader = LoaderFactory.create(loader_type)
        snapshot = loader.load(path)

        # Merge into registry
        self._registry.merge(snapshot)

        # Clear cache (snapshot changed)
        self._cache.clear()

        return snapshot

    def load_from_env(
        self,
        prefix: str = "",
    ) -> ConfigurationSnapshot:
        """Load configuration from environment variables."""

        loader = LoaderFactory.create("env", prefix=prefix)
        snapshot = loader.load()

        self._registry.merge(snapshot)
        self._cache.clear()

        return snapshot

    def load_all(
        self,
    ) -> ConfigurationSnapshot:
        """
        Load configuration from all registered sources.

        Sources are loaded in priority order
        (lowest first), so higher priority
        sources override lower ones.

        Returns:
            Merged ConfigurationSnapshot.
        """

        snapshot = self._multi_loader.load_all()
        self._registry.merge(snapshot)
        self._cache.clear()
        return snapshot

    def add_source(
        self,
        path: str,
        loader_type: str = "yaml",
    ) -> None:
        """Add a file source to the multi-source loader."""

        self._multi_loader.add_file(path, loader_type)

    def add_env_source(
        self,
        prefix: str = "",
    ) -> None:
        """Add environment variable source."""

        self._multi_loader.add_env(prefix=prefix)

    # ── Validation ──

    def validate(
        self,
    ) -> ValidationResult:
        """
        Validate current configuration.

        Executes all registered validation
        rules against the current snapshot.

        Returns:
            ValidationResult with any errors.
        """

        snapshot = self._registry.get_snapshot()
        return self._validator.validate(snapshot)

    def add_validation_rule(
        self,
        rule: Any,
    ) -> None:
        """Add a validation rule."""

        self._validator.add_rule(rule)

    # ── Cache Management ──

    def clear_cache(
        self,
    ) -> None:
        """Clear the configuration cache."""
        self._cache.clear()

    def cleanup_cache(
        self,
    ) -> int:
        """Remove expired cache entries."""
        return self._cache.cleanup_expired()

    def cache_stats(
        self,
    ) -> Dict[str, Any]:
        """Get cache statistics."""
        return self._cache.get_stats()

    # ── Rollback ──

    def rollback(
        self,
        steps: int = 1,
    ) -> bool:
        """
        Rollback to a previous configuration.

        Args:
            steps: Number of versions to rollback.

        Returns:
            True if rollback succeeded.
        """

        result = self._registry.rollback(steps=steps)
        if result:
            self._cache.clear()
        return result

    # ── Status ──

    def get_stats(
        self,
    ) -> Dict[str, Any]:
        """Get manager statistics."""

        return {
            "environment": self._registry.environment,
            "items": self._registry.item_count,
            "version": self._registry.snapshot_version,
            "cache": self._cache.get_stats(),
            "validator_rules": self._validator.rule_count,
            "sources": len(self._multi_loader._sources),
        }

    def _detect_loader_type(
        self,
        path: str,
    ) -> str:
        """Auto-detect loader type from file extension."""

        ext = path.rsplit(".", 1)[-1].lower() if "." in path else ""
        mapping = {
            "yaml": "yaml",
            "yml": "yaml",
            "json": "json",
            "toml": "toml",
        }
        return mapping.get(ext, self._config.default_loader)
