"""
Feature flag platform storage abstraction.

Provides a unified interface for loading and
saving feature flag definitions across multiple
backends (memory, YAML, database, Redis, remote).
"""

from __future__ import annotations

import asyncio
import json
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional

from .constants import StorageBackend
from .exceptions import FeatureFlagStorageError
from .models import FeatureFlag

logger = logging.getLogger(__name__)


class FeatureStorage(ABC):
    """
    Abstract storage backend for feature flags.

    Defines the interface that all storage backends
    must implement for loading, saving, and managing
    feature flag definitions.
    """

    @abstractmethod
    async def load(self) -> Dict[str, FeatureFlag]:
        """
        Load all feature flags from storage.

        Returns:
            Dictionary mapping flag keys to FeatureFlag objects.
        """

    @abstractmethod
    async def save(
        self,
        flags: Dict[str, FeatureFlag],
    ) -> None:
        """
        Save feature flags to storage.

        Args:
            flags: Dictionary mapping flag keys to FeatureFlag objects.
        """

    @abstractmethod
    async def upsert(
        self,
        flag: FeatureFlag,
    ) -> None:
        """
        Insert or update a single feature flag.

        Args:
            flag: Feature flag to save.
        """

    @abstractmethod
    async def delete(
        self,
        key: str,
    ) -> bool:
        """
        Delete a feature flag by key.

        Args:
            key: Flag key to delete.

        Returns:
            True if the flag was deleted.
        """

    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """
        Check storage backend health.

        Returns:
            Health status dictionary.
        """

    async def start(self) -> None:
        """Initialize the storage backend."""

    async def shutdown(self) -> None:
        """Shutdown the storage backend."""


class MemoryFeatureStorage(FeatureStorage):
    """
    In-memory storage backend for feature flags.

    Stores all flags in a dictionary in memory.
    Suitable for development and testing.
    """

    def __init__(self) -> None:
        self._flags: Dict[str, FeatureFlag] = {}
        self._lock = asyncio.Lock()
        self._initialized = False

    async def start(self) -> None:
        """Initialize the memory storage."""
        async with self._lock:
            self._initialized = True
            logger.info("MemoryFeatureStorage started")

    async def shutdown(self) -> None:
        """Shutdown the memory storage."""
        async with self._lock:
            self._flags.clear()
            self._initialized = False
            logger.info("MemoryFeatureStorage shutdown")

    async def load(self) -> Dict[str, FeatureFlag]:
        """Load all feature flags from memory."""
        async with self._lock:
            return dict(self._flags)

    async def save(
        self,
        flags: Dict[str, FeatureFlag],
    ) -> None:
        """Save all feature flags to memory."""
        async with self._lock:
            self._flags = dict(flags)

    async def upsert(
        self,
        flag: FeatureFlag,
    ) -> None:
        """Insert or update a single feature flag."""
        async with self._lock:
            self._flags[flag.key] = flag

    async def delete(
        self,
        key: str,
    ) -> bool:
        """Delete a feature flag by key."""
        async with self._lock:
            if key in self._flags:
                del self._flags[key]
                return True
            return False

    async def health_check(self) -> Dict[str, Any]:
        """Check memory storage health."""
        async with self._lock:
            return {
                "healthy": self._initialized,
                "backend": "memory",
                "flag_count": len(self._flags),
            }


class YAMLFeatureStorage(FeatureStorage):
    """
    YAML file-based storage backend for feature flags.

    Loads and saves feature flags to a YAML file.
    Suitable for configuration-as-code workflows.
    """

    def __init__(
        self,
        file_path: str = "feature_flags.yaml",
    ) -> None:
        self._file_path = file_path
        self._flags: Dict[str, FeatureFlag] = {}
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        """Load flags from YAML file."""
        try:
            flags = await self._load_from_file()
            async with self._lock:
                self._flags = flags
            logger.info(
                "YAMLFeatureStorage loaded %d flags from %s",
                len(flags), self._file_path,
            )
        except FileNotFoundError:
            logger.info(
                "YAML file not found: %s. Starting empty.",
                self._file_path,
            )
            async with self._lock:
                self._flags = {}

    async def shutdown(self) -> None:
        """Save flags to YAML file."""
        async with self._lock:
            await self._save_to_file(self._flags)
            logger.info(
                "YAMLFeatureStorage saved %d flags to %s",
                len(self._flags), self._file_path,
            )

    async def load(self) -> Dict[str, FeatureFlag]:
        """Load all feature flags from storage."""
        async with self._lock:
            return dict(self._flags)

    async def save(
        self,
        flags: Dict[str, FeatureFlag],
    ) -> None:
        """Save all feature flags to storage."""
        async with self._lock:
            self._flags = dict(flags)
            await self._save_to_file(self._flags)

    async def upsert(
        self,
        flag: FeatureFlag,
    ) -> None:
        """Insert or update a single feature flag."""
        async with self._lock:
            self._flags[flag.key] = flag
            await self._save_to_file(self._flags)

    async def delete(
        self,
        key: str,
    ) -> bool:
        """Delete a feature flag by key."""
        async with self._lock:
            if key in self._flags:
                del self._flags[key]
                await self._save_to_file(self._flags)
                return True
            return False

    async def health_check(self) -> Dict[str, Any]:
        """Check YAML storage health."""
        return {
            "healthy": True,
            "backend": "yaml",
            "file_path": self._file_path,
            "flag_count": len(self._flags),
        }

    async def _load_from_file(self) -> Dict[str, FeatureFlag]:
        """Load flags from YAML file."""
        import yaml

        try:
            with open(self._file_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        except FileNotFoundError:
            return {}

        flags: Dict[str, FeatureFlag] = {}
        for key, raw in data.get("flags", {}).items():
            flags[key] = self._dict_to_flag(key, raw)
        return flags

    async def _save_to_file(
        self,
        flags: Dict[str, FeatureFlag],
    ) -> None:
        """Save flags to YAML file."""
        import yaml

        data = {"flags": {}}
        for key, flag in flags.items():
            data["flags"][key] = self._flag_to_dict(flag)

        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(None, self._write_yaml, data)
        except Exception as e:
            raise FeatureFlagStorageError(
                operation="save",
                backend="yaml",
                reason=str(e),
            )

    def _write_yaml(self, data: Dict[str, Any]) -> None:
        """Write data to YAML file (blocking)."""
        import yaml

        with open(self._file_path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True)

    def _dict_to_flag(
        self,
        key: str,
        data: Dict[str, Any],
    ) -> FeatureFlag:
        """Convert a dictionary to a FeatureFlag."""
        from .constants import FeatureFlagType, FlagStatus

        return FeatureFlag(
            key=key,
            enabled=data.get("enabled", True),
            description=data.get("description", ""),
            flag_type=FeatureFlagType(data.get("flag_type", "boolean")),
            default_value=data.get("default_value", True),
            tags=frozenset(data.get("tags", [])),
            status=FlagStatus(data.get("status", "active")),
        )

    def _flag_to_dict(self, flag: FeatureFlag) -> Dict[str, Any]:
        """Convert a FeatureFlag to a dictionary."""
        return {
            "enabled": flag.enabled,
            "description": flag.description,
            "flag_type": flag.flag_type.value,
            "default_value": flag.default_value,
            "tags": list(flag.tags),
            "status": flag.status.value,
            "updated_at": flag.updated_at.isoformat() if flag.updated_at else None,
        }


class DatabaseFeatureStorage(FeatureStorage):
    """
    Database-backed storage backend for feature flags.

    Placeholder for future implementation with
    PostgreSQL or SQLite support.
    """

    def __init__(self) -> None:
        self._flags: Dict[str, FeatureFlag] = {}
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        """Initialize database storage."""
        logger.info("DatabaseFeatureStorage started (placeholder)")

    async def shutdown(self) -> None:
        """Shutdown database storage."""
        async with self._lock:
            self._flags.clear()

    async def load(self) -> Dict[str, FeatureFlag]:
        """Load all feature flags."""
        async with self._lock:
            return dict(self._flags)

    async def save(
        self,
        flags: Dict[str, FeatureFlag],
    ) -> None:
        """Save all feature flags."""
        async with self._lock:
            self._flags = dict(flags)

    async def upsert(
        self,
        flag: FeatureFlag,
    ) -> None:
        """Insert or update a single feature flag."""
        async with self._lock:
            self._flags[flag.key] = flag

    async def delete(
        self,
        key: str,
    ) -> bool:
        """Delete a feature flag."""
        async with self._lock:
            if key in self._flags:
                del self._flags[key]
                return True
            return False

    async def health_check(self) -> Dict[str, Any]:
        """Check database storage health."""
        return {
            "healthy": True,
            "backend": "database",
            "flag_count": len(self._flags),
        }


class RedisFeatureStorage(FeatureStorage):
    """
    Redis-backed storage backend for feature flags.

    Placeholder for future implementation with
    Redis support for distributed flag management.
    """

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379",
    ) -> None:
        self._redis_url = redis_url
        self._flags: Dict[str, FeatureFlag] = {}
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        """Initialize Redis storage."""
        logger.info(
            "RedisFeatureStorage started (placeholder) at %s",
            self._redis_url,
        )

    async def shutdown(self) -> None:
        """Shutdown Redis storage."""
        async with self._lock:
            self._flags.clear()

    async def load(self) -> Dict[str, FeatureFlag]:
        """Load all feature flags."""
        async with self._lock:
            return dict(self._flags)

    async def save(
        self,
        flags: Dict[str, FeatureFlag],
    ) -> None:
        """Save all feature flags."""
        async with self._lock:
            self._flags = dict(flags)

    async def upsert(
        self,
        flag: FeatureFlag,
    ) -> None:
        """Insert or update a single feature flag."""
        async with self._lock:
            self._flags[flag.key] = flag

    async def delete(
        self,
        key: str,
    ) -> bool:
        """Delete a feature flag."""
        async with self._lock:
            if key in self._flags:
                del self._flags[key]
                return True
            return False

    async def health_check(self) -> Dict[str, Any]:
        """Check Redis storage health."""
        return {
            "healthy": True,
            "backend": "redis",
            "flag_count": len(self._flags),
            "redis_url": self._redis_url,
        }


class RemoteFeatureStorage(FeatureStorage):
    """
    Remote configuration center storage backend.

    Placeholder for future implementation with
    remote config services (etcd, Consul, Apollo, etc).
    """

    def __init__(
        self,
        remote_url: str = "http://localhost:8080",
    ) -> None:
        self._remote_url = remote_url
        self._flags: Dict[str, FeatureFlag] = {}
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        """Initialize remote storage."""
        logger.info(
            "RemoteFeatureStorage started (placeholder) at %s",
            self._remote_url,
        )

    async def shutdown(self) -> None:
        """Shutdown remote storage."""
        async with self._lock:
            self._flags.clear()

    async def load(self) -> Dict[str, FeatureFlag]:
        """Load all feature flags."""
        async with self._lock:
            return dict(self._flags)

    async def save(
        self,
        flags: Dict[str, FeatureFlag],
    ) -> None:
        """Save all feature flags."""
        async with self._lock:
            self._flags = dict(flags)

    async def upsert(
        self,
        flag: FeatureFlag,
    ) -> None:
        """Insert or update a single feature flag."""
        async with self._lock:
            self._flags[flag.key] = flag

    async def delete(
        self,
        key: str,
    ) -> bool:
        """Delete a feature flag."""
        async with self._lock:
            if key in self._flags:
                del self._flags[key]
                return True
            return False

    async def health_check(self) -> Dict[str, Any]:
        """Check remote storage health."""
        return {
            "healthy": True,
            "backend": "remote",
            "flag_count": len(self._flags),
            "remote_url": self._remote_url,
        }


def create_storage(
    backend: StorageBackend,
    **kwargs: Any,
) -> FeatureStorage:
    """
    Factory function to create a storage backend.

    Args:
        backend: Storage backend type.
        **kwargs: Backend-specific arguments.

    Returns:
        Configured FeatureStorage instance.
    """
    backends: Dict[StorageBackend, type] = {
        StorageBackend.MEMORY: MemoryFeatureStorage,
        StorageBackend.YAML: YAMLFeatureStorage,
        StorageBackend.DATABASE: DatabaseFeatureStorage,
        StorageBackend.REDIS: RedisFeatureStorage,
        StorageBackend.REMOTE: RemoteFeatureStorage,
    }

    storage_class = backends.get(backend)
    if storage_class is None:
        raise ValueError(f"Unknown storage backend: {backend}")

    if backend == StorageBackend.YAML:
        return storage_class(file_path=kwargs.get("file_path", "feature_flags.yaml"))
    elif backend == StorageBackend.REDIS:
        return storage_class(redis_url=kwargs.get("redis_url", "redis://localhost:6379"))
    elif backend == StorageBackend.REMOTE:
        return storage_class(remote_url=kwargs.get("remote_url", "http://localhost:8080"))
    else:
        return storage_class()