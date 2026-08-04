"""
Configuration loaders.

Provides loaders for multiple configuration
file formats and sources:

    YAML  - YAML configuration files
    JSON  - JSON configuration files
    TOML  - TOML configuration files
    ENV   - Environment variables

Each loader implements the ConfigurationLoader
interface, enabling pluggable configuration
sources.

Usage:
    loader = YAMLLoader()
    config = loader.load("config.yaml")

    loader = JSONLoader()
    config = loader.load("config.json")
"""

from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional

from .constants import ConfigSource, LoaderType
from .exceptions import ConfigLoadError, ConfigParseError
from .models import ConfigurationItem, ConfigurationSnapshot


class ConfigurationLoader(ABC):
    """
    Abstract configuration loader.

    All loaders inherit from this base class
    and implement the load() method.
    """

    loader_type: str = "abstract"

    @abstractmethod
    def load(
        self,
        source: str,
    ) -> ConfigurationSnapshot:
        """
        Load configuration from a source.

        Args:
            source: Source path or identifier.

        Returns:
            ConfigurationSnapshot with loaded items.
        """

        ...


# ── YAML Loader ──


class YAMLLoader(ConfigurationLoader):
    """Load configuration from YAML files."""

    loader_type = LoaderType.YAML.value

    def load(
        self,
        source: str,
    ) -> ConfigurationSnapshot:
        """
        Load configuration from a YAML file.

        Args:
            source: Path to YAML file.

        Returns:
            ConfigurationSnapshot with loaded items.

        Raises:
            ConfigLoadError: If file cannot be read.
            ConfigParseError: If YAML parsing fails.
        """

        path = Path(source)
        if not path.exists():
            raise ConfigLoadError(source, "File not found")

        try:
            content = path.read_text(encoding="utf-8")
        except OSError as e:
            raise ConfigLoadError(source, str(e))

        try:
            import yaml
            data = yaml.safe_load(content)
        except ImportError:
            raise ConfigLoadError(
                source,
                "PyYAML not installed (pip install pyyaml)",
            )
        except yaml.YAMLError as e:
            raise ConfigParseError(source, str(e))

        if not isinstance(data, dict):
            data = {} if data is None else {"value": data}

        return self._dict_to_snapshot(data, source)

    def load_string(
        self,
        content: str,
    ) -> ConfigurationSnapshot:
        """Load configuration from a YAML string."""

        try:
            import yaml
            data = yaml.safe_load(content)
        except ImportError:
            raise ConfigLoadError("string", "PyYAML not installed")
        except yaml.YAMLError as e:
            raise ConfigParseError("string", str(e))

        if not isinstance(data, dict):
            data = {} if data is None else {"value": data}

        return self._dict_to_snapshot(data, "string")

    def _dict_to_snapshot(
        self,
        data: Dict[str, Any],
        source: str,
    ) -> ConfigurationSnapshot:
        """Convert flat dictionary to snapshot."""

        items: Dict[str, ConfigurationItem] = {}
        for key, value in data.items():
            items[key] = ConfigurationItem(
                key=key,
                value=value,
                source=ConfigSource.FILE.value,
            )

        return ConfigurationSnapshot(
            items=items,
            source=source,
        )


# ── JSON Loader ──


class JSONLoader(ConfigurationLoader):
    """Load configuration from JSON files."""

    loader_type = LoaderType.JSON.value

    def load(
        self,
        source: str,
    ) -> ConfigurationSnapshot:
        """
        Load configuration from a JSON file.

        Args:
            source: Path to JSON file.

        Returns:
            ConfigurationSnapshot with loaded items.
        """

        path = Path(source)
        if not path.exists():
            raise ConfigLoadError(source, "File not found")

        try:
            content = path.read_text(encoding="utf-8")
        except OSError as e:
            raise ConfigLoadError(source, str(e))

        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            raise ConfigParseError(source, str(e))

        if not isinstance(data, dict):
            data = {} if data is None else {"value": data}

        return self._dict_to_snapshot(data, source)

    def load_string(
        self,
        content: str,
    ) -> ConfigurationSnapshot:
        """Load configuration from a JSON string."""

        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            raise ConfigParseError("string", str(e))

        if not isinstance(data, dict):
            data = {} if data is None else {"value": data}

        return self._dict_to_snapshot(data, "string")

    def _dict_to_snapshot(
        self,
        data: Dict[str, Any],
        source: str,
    ) -> ConfigurationSnapshot:

        items: Dict[str, ConfigurationItem] = {}
        for key, value in data.items():
            items[key] = ConfigurationItem(
                key=key,
                value=value,
                source=ConfigSource.FILE.value,
            )

        return ConfigurationSnapshot(
            items=items,
            source=source,
        )


# ── TOML Loader ──


class TOMLLoader(ConfigurationLoader):
    """Load configuration from TOML files."""

    loader_type = LoaderType.TOML.value

    def load(
        self,
        source: str,
    ) -> ConfigurationSnapshot:
        """
        Load configuration from a TOML file.

        Args:
            source: Path to TOML file.

        Returns:
            ConfigurationSnapshot with loaded items.
        """

        path = Path(source)
        if not path.exists():
            raise ConfigLoadError(source, "File not found")

        try:
            content = path.read_text(encoding="utf-8")
        except OSError as e:
            raise ConfigLoadError(source, str(e))

        try:
            try:
                import tomllib
                data = tomllib.loads(content)
            except ImportError:
                import toml
                data = toml.loads(content)
        except ImportError:
            raise ConfigLoadError(
                source,
                "toml/tomllib not installed",
            )
        except Exception as e:
            raise ConfigParseError(source, str(e))

        items: Dict[str, ConfigurationItem] = {}
        for key, value in data.items():
            items[key] = ConfigurationItem(
                key=key,
                value=value,
                source=ConfigSource.FILE.value,
            )

        return ConfigurationSnapshot(
            items=items,
            source=source,
        )


# ── ENV Loader ──


class EnvLoader(ConfigurationLoader):
    """Load configuration from environment variables."""

    loader_type = LoaderType.ENV.value

    def __init__(
        self,
        prefix: str = "",
    ) -> None:
        """
        Initialize ENV loader.

        Args:
            prefix: Only load env vars with this prefix
                    (e.g., "ICYQUANT_" for ICYQUANT_PORT=8080).
        """

        self._prefix = prefix

    def load(
        self,
        source: str = "",
    ) -> ConfigurationSnapshot:
        """
        Load configuration from environment variables.

        Args:
            source: Ignored (loads from os.environ).

        Returns:
            ConfigurationSnapshot with env var items.
        """

        items: Dict[str, ConfigurationItem] = {}

        for key, value in os.environ.items():
            if self._prefix and not key.startswith(self._prefix):
                continue

            # Strip prefix from key
            config_key = key[len(self._prefix):].lower() if self._prefix else key.lower()

            # Try to parse as JSON, fall back to string
            parsed_value = self._parse_value(value)

            items[config_key] = ConfigurationItem(
                key=config_key,
                value=parsed_value,
                source=ConfigSource.ENV.value,
            )

        return ConfigurationSnapshot(
            items=items,
            source="environment",
        )

    def _parse_value(
        self,
        value: str,
    ) -> Any:
        """Parse string value to appropriate type."""

        # Try JSON first (handles numbers, booleans, null)
        try:
            return json.loads(value)
        except (json.JSONDecodeError, ValueError):
            pass

        return value


# ── Loader Factory ──


class LoaderFactory:
    """Factory for creating configuration loaders."""

    _loaders = {
        LoaderType.YAML.value: YAMLLoader,
        LoaderType.JSON.value: JSONLoader,
        LoaderType.TOML.value: TOMLLoader,
        LoaderType.ENV.value: EnvLoader,
    }

    @staticmethod
    def create(
        loader_type: str,
        **kwargs,
    ) -> ConfigurationLoader:
        """
        Create a loader by type.

        Args:
            loader_type: Loader type (yaml/json/toml/env).
            **kwargs: Additional loader arguments.

        Returns:
            ConfigurationLoader instance.

        Raises:
            ValueError: If loader type is unknown.
        """

        loader_cls = LoaderFactory._loaders.get(loader_type)
        if loader_cls is None:
            raise ValueError(
                f"Unknown loader type: {loader_type}. "
                f"Supported: {list(LoaderFactory._loaders.keys())}"
            )
        return loader_cls(**kwargs)

    @staticmethod
    def supported_types(
    ) -> List[str]:
        """Get list of supported loader types."""
        return list(LoaderFactory._loaders.keys())

    @staticmethod
    def register(
        loader_type: str,
        loader_cls: type,
    ) -> None:
        """Register a custom loader."""

        LoaderFactory._loaders[loader_type] = loader_cls


# ── Multi-Source Loader ──


class MultiSourceLoader:
    """
    Multi-source configuration loader.

    Loads configuration from multiple sources
    and merges them based on source priority:

        CLI > ENV > SECRETS > REMOTE > FILE > DEFAULT

    Higher priority sources override
    lower priority sources.

    This is the legacy loader that works with
    the original ConfigurationSnapshot model
    (with items dict).

    Usage:
        loader = MultiSourceLoader()
        loader.add_file("config.yaml", LoaderType.YAML)
        loader.add_file("config.local.json", LoaderType.JSON)
        loader.add_env(prefix="ICYQUANT_")

        snapshot = loader.load_all()
    """

    def __init__(
        self,
    ) -> None:
        self._sources: List[tuple] = []

    def add_file(
        self,
        path: str,
        loader_type: str = LoaderType.YAML.value,
    ) -> None:
        """Add a file source."""

        loader = LoaderFactory.create(loader_type)
        self._sources.append((ConfigSource.FILE, path, loader))

    def add_env(
        self,
        prefix: str = "",
    ) -> None:
        """Add environment variable source."""

        loader = EnvLoader(prefix=prefix)
        self._sources.append((ConfigSource.ENV, "", loader))

    def add_loader(
        self,
        source: ConfigSource,
        path: str,
        loader: ConfigurationLoader,
    ) -> None:
        """Add a custom loader."""

        self._sources.append((source, path, loader))

    def load_all(
        self,
    ) -> ConfigurationSnapshot:
        """
        Load and merge all sources.

        Returns:
            Merged ConfigurationSnapshot.
        """

        sorted_sources = sorted(
            self._sources,
            key=lambda x: x[0].priority,
        )

        merged = ConfigurationSnapshot()

        for source_type, path, loader in sorted_sources:
            try:
                snapshot = loader.load(path) if path else loader.load()
                merged = merged.merge(snapshot)
            except Exception:
                pass

        return merged


# ── Unified Configuration Loader (Part 1.2) ──


class UnifiedConfigurationLoader:
    """
    Unified configuration loader using the new
    multi-source resolution framework.

    Integrates ConfigurationResolver with
    ConfigurationMerger and SnapshotStore for
    production-grade configuration loading.

    Usage:
        loader = UnifiedConfigurationLoader()
        loader.add_source(DefaultsSource())
        loader.add_source(YAMLSource("config.yaml"))
        loader.add_source(EnvironmentSource(prefix="ICYQUANT_"))
        loader.add_source(CLISource())

        snapshot = await loader.load()
        # snapshot is an immutable ConfigurationSnapshot
    """

    def __init__(
        self,
    ) -> None:
        """Initialize unified loader."""
        from .resolver import ConfigurationResolver
        from .cache import SnapshotCache

        self._resolver = ConfigurationResolver()
        self._cache = SnapshotCache()

    @property
    def resolver(
        self,
    ) -> Any:
        """Get configuration resolver."""
        return self._resolver

    @property
    def cache(
        self,
    ) -> SnapshotCache:
        """Get snapshot cache."""
        return self._cache

    def add_source(
        self,
        source: Any,
    ) -> None:
        """Add a configuration source."""
        self._resolver.add_source(source)

    def add_sources(
        self,
        sources: List[Any],
    ) -> None:
        """Add multiple sources."""
        self._resolver.add_sources(sources)

    async def load(
        self,
    ) -> Any:
        """
        Load and resolve configuration from all sources.

        Returns:
            Immutable ConfigurationSnapshot with merged values.
        """
        from .snapshot import ConfigurationSnapshot

        # Resolve from all sources
        resolved_snapshot = await self._resolver.resolve()

        # Update cache
        cached_snapshot = self._cache.update(
            values=resolved_snapshot.values,
            environment=resolved_snapshot.environment,
            sources_used=resolved_snapshot.sources_used,
        )

        return cached_snapshot

    async def reload(
        self,
    ) -> Any:
        """
        Reload configuration from all sources.

        Returns:
            Updated ConfigurationSnapshot.
        """
        return await self.load()

    def get_current(
        self,
    ) -> Any:
        """Get current cached snapshot."""
        return self._cache.current

    def rollback(
        self,
        steps: int = 1,
    ) -> Any:
        """Rollback to a previous version."""
        return self._cache.rollback(steps)
