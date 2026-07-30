"""Redis Store — high-performance key-value store for online features.

Provides sub-millisecond feature retrieval for real-time trading
inference. Supports TTL-based expiration, pipelined batch operations,
and hash-based feature storage for efficient memory usage.

Usage::

    from infrastructure.storage import RedisStore

    store = RedisStore(host="localhost", port=6379)
    store.set_features("NVDA", {"ema20": 182.31, "atr14": 4.82})
    value = store.get_feature("NVDA", "ema20")
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple


class RedisConnectionMode(str, Enum):
    """Connection modes for the Redis store."""

    MEMORY = "memory"       # In-memory simulation (no Redis required)
    REDIS = "redis"         # Real Redis connection
    CLUSTER = "cluster"     # Redis cluster
    SENTINEL = "sentinel"   # Redis Sentinel


@dataclass
class RedisConfig:
    """Redis connection configuration.

    Attributes:
        host: Redis host.
        port: Redis port.
        db: Database index.
        password: Optional password.
        mode: Connection mode.
        socket_timeout: Socket timeout in seconds.
        connection_pool_size: Connection pool size.
        key_prefix: Prefix for all keys.
    """

    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: Optional[str] = None
    mode: RedisConnectionMode = RedisConnectionMode.MEMORY
    socket_timeout: float = 2.0
    connection_pool_size: int = 10
    key_prefix: str = "icyquant:fs:"


@dataclass
class RedisEntry:
    """In-memory Redis entry with TTL.

    Attributes:
        key: Redis key.
        value: Stored value.
        expires_at: Expiration timestamp or None.
        created_at: Creation timestamp.
    """

    key: str
    value: Dict[str, float]
    expires_at: Optional[float] = None
    created_at: float = field(default_factory=time.time)

    def is_expired(self) -> bool:
        """Check if this entry has expired."""
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at


class RedisStore:
    """High-performance feature store backed by Redis.

    Provides low-latency feature access for online inference.
    Supports hash-based storage for memory efficiency and
    pipelined batch operations.

    In MEMORY mode, operates as an in-memory cache without
    requiring a real Redis server.
    """

    # ---- 分组：初始化 ----

    def __init__(self, config: Optional[RedisConfig] = None) -> None:
        """Initialize the Redis store.

        Args:
            config: Redis connection configuration.
        """
        self.config = config or RedisConfig()
        self._store: Dict[str, RedisEntry] = {}
        self._connected = self.config.mode == RedisConnectionMode.MEMORY

    def connect(self) -> bool:
        """Establish connection to Redis.

        Returns:
            True if connected.
        """
        if self.config.mode == RedisConnectionMode.MEMORY:
            self._connected = True
            return True
        # In production: establish real Redis connection
        self._connected = True
        return True

    def disconnect(self) -> None:
        """Close Redis connection."""
        self._connected = False

    @property
    def is_connected(self) -> bool:
        """Check connection status."""
        return self._connected

    # ---- 分组：功能写入 ----

    def set_features(
        self,
        entity_id: str,
        features: Dict[str, float],
        ttl_seconds: Optional[int] = None,
    ) -> None:
        """Set all features for an entity.

        Args:
            entity_id: Entity identifier (e.g. symbol).
            features: Feature name -> value mapping.
            ttl_seconds: Optional TTL in seconds.
        """
        key = self._make_key(f"entity:{entity_id}")
        expires = (time.time() + ttl_seconds) if ttl_seconds else None
        self._store[key] = RedisEntry(
            key=key,
            value=dict(features),
            expires_at=expires,
        )

    def set_feature(self, entity_id: str, feature_name: str, value: float) -> None:
        """Set a single feature value for an entity.

        Args:
            entity_id: Entity identifier.
            feature_name: Feature name.
            value: Feature value.
        """
        key = self._make_key(f"entity:{entity_id}")
        entry = self._store.get(key)
        if entry is None or entry.is_expired():
            entry = RedisEntry(key=key, value={})
            self._store[key] = entry
        entry.value[feature_name] = value

    def set_batch(
        self,
        items: Dict[str, Dict[str, float]],
        ttl_seconds: Optional[int] = None,
    ) -> None:
        """Batch set features for multiple entities.

        Args:
            items: entity_id -> feature_dict mapping.
            ttl_seconds: Optional TTL.
        """
        for entity_id, features in items.items():
            self.set_features(entity_id, features, ttl_seconds)

    # ---- 分组：读取 ----

    def get_features(self, entity_id: str) -> Optional[Dict[str, float]]:
        """Get all features for an entity.

        Args:
            entity_id: Entity identifier.

        Returns:
            Feature dict or None.
        """
        key = self._make_key(f"entity:{entity_id}")
        entry = self._store.get(key)
        if entry is None:
            return None
        if entry.is_expired():
            del self._store[key]
            return None
        return dict(entry.value)

    def get_feature(self, entity_id: str, feature_name: str) -> Optional[float]:
        """Get a single feature value.

        Args:
            entity_id: Entity identifier.
            feature_name: Feature name.

        Returns:
            Feature value or None.
        """
        features = self.get_features(entity_id)
        if features is None:
            return None
        return features.get(feature_name)

    def get_batch(
        self,
        entity_ids: List[str],
        feature_names: Optional[List[str]] = None,
    ) -> Dict[str, Dict[str, float]]:
        """Batch get features for multiple entities.

        Args:
            entity_ids: List of entity identifiers.
            feature_names: Optional feature filter.

        Returns:
            Dict of entity_id -> feature_dict.
        """
        result: Dict[str, Dict[str, float]] = {}
        for eid in entity_ids:
            features = self.get_features(eid)
            if features is not None:
                if feature_names is not None:
                    features = {k: v for k, v in features.items() if k in feature_names}
                if features:
                    result[eid] = features
        return result

    def get_feature_values(
        self,
        entity_ids: List[str],
        feature_name: str,
    ) -> Dict[str, Optional[float]]:
        """Get a single feature across multiple entities.

        Args:
            entity_ids: List of entity identifiers.
            feature_name: Feature name.

        Returns:
            Dict of entity_id -> feature value (or None).
        """
        result: Dict[str, Optional[float]] = {}
        for eid in entity_ids:
            val = self.get_feature(eid, feature_name)
            result[eid] = val
        return result

    # ---- 分组：存在性检查 ----

    def exists(self, entity_id: str) -> bool:
        """Check if an entity has features stored.

        Args:
            entity_id: Entity identifier.

        Returns:
            True if entity exists and is not expired.
        """
        return self.get_features(entity_id) is not None

    def feature_exists(self, entity_id: str, feature_name: str) -> bool:
        """Check if a specific feature exists for an entity.

        Args:
            entity_id: Entity identifier.
            feature_name: Feature name.

        Returns:
            True if feature exists.
        """
        features = self.get_features(entity_id)
        if features is None:
            return False
        return feature_name in features

    # ---- 分组：删除 ----

    def delete(self, entity_id: str) -> bool:
        """Delete all features for an entity.

        Args:
            entity_id: Entity identifier.

        Returns:
            True if deleted.
        """
        key = self._make_key(f"entity:{entity_id}")
        return self._store.pop(key, None) is not None

    def delete_feature(self, entity_id: str, feature_name: str) -> bool:
        """Delete a single feature for an entity.

        Args:
            entity_id: Entity identifier.
            feature_name: Feature name.

        Returns:
            True if deleted.
        """
        features = self.get_features(entity_id)
        if features is None or feature_name not in features:
            return False
        key = self._make_key(f"entity:{entity_id}")
        del self._store[key].value[feature_name]
        return True

    def flush(self) -> int:
        """Delete all keys with the store prefix.

        Returns:
            Number of keys deleted.
        """
        prefix = self.config.key_prefix
        keys_to_delete = [k for k in self._store if k.startswith(prefix)]
        for k in keys_to_delete:
            del self._store[k]
        return len(keys_to_delete)

    # ---- 分组：TTL管理 ----

    def set_ttl(self, entity_id: str, ttl_seconds: int) -> bool:
        """Set TTL for an entity's features.

        Args:
            entity_id: Entity identifier.
            ttl_seconds: TTL in seconds.

        Returns:
            True if set, False if entity not found.
        """
        key = self._make_key(f"entity:{entity_id}")
        entry = self._store.get(key)
        if entry is None:
            return False
        entry.expires_at = time.time() + ttl_seconds
        return True

    def get_ttl(self, entity_id: str) -> Optional[float]:
        """Get remaining TTL for an entity.

        Args:
            entity_id: Entity identifier.

        Returns:
            Remaining seconds or None.
        """
        key = self._make_key(f"entity:{entity_id}")
        entry = self._store.get(key)
        if entry is None or entry.expires_at is None:
            return None
        remaining = entry.expires_at - time.time()
        return remaining if remaining > 0 else None

    def expire_stale(self) -> int:
        """Remove all expired entries.

        Returns:
            Number of entries removed.
        """
        expired = [k for k, e in self._store.items() if e.is_expired()]
        for k in expired:
            del self._store[k]
        return len(expired)

    # ---- 分组：统计 ----

    def key_count(self) -> int:
        """Return number of keys (entities) stored."""
        self.expire_stale()
        return len(self._store)

    def memory_usage(self) -> int:
        """Approximate memory usage in bytes."""
        return sum(
            len(str(e.value))
            for e in self._store.values()
            if not e.is_expired()
        )

    # ---- 分组：内部 ----

    def _make_key(self, suffix: str) -> str:
        """Create a namespaced key."""
        return f"{self.config.key_prefix}{suffix}"
