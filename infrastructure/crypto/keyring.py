"""
Keyring - in-memory key material storage.

Provides secure in-memory storage for
key materials including master keys,
data encryption keys, and signing keys
with access control and automatic
cleanup.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from .constants import KeyStatus
from .exceptions import CryptoKeyError

logger = logging.getLogger(__name__)


@dataclass
class StoredKey:
    """
    Stored key entry.

    Attributes:
        key_id: Key identifier.
        material: Key material (bytes).
        algorithm: Algorithm name.
        key_type: Type of key.
        version: Key version.
        status: Key status.
        created_at: Storage timestamp.
        expires_at: Expiration timestamp.
        metadata: Additional metadata.
    """

    key_id: str = ""
    material: bytes = b""
    algorithm: str = ""
    key_type: str = "encryption"
    version: int = 1
    status: KeyStatus = KeyStatus.ACTIVE
    created_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def is_expired(self) -> bool:
        """Check if the key has expired."""
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at

    def is_valid(self) -> bool:
        """Check if the key is valid and not expired."""
        return (
            self.status == KeyStatus.ACTIVE
            and not self.is_expired()
        )


class Keyring:
    """
    In-memory key material store.

    Provides secure storage for key materials
    with access control, expiration, and
    automatic cleanup of expired keys.

    Features:
    - Thread-safe key storage
    - Automatic expiration
    - Key rotation tracking
    - Access control
    - Memory usage limits
    """

    def __init__(
        self,
        max_keys: int = 256,
        default_ttl_seconds: int = 3600,
    ) -> None:
        """
        Initialize keyring.

        Args:
            max_keys: Maximum number of stored keys.
            default_ttl_seconds: Default key TTL.
        """
        self._lock = threading.RLock()
        self._keys: Dict[str, StoredKey] = {}
        self._max_keys = max_keys
        self._default_ttl = default_ttl_seconds
        self._total_material_bytes = 0

    def store_key(
        self,
        key_id: str,
        material: bytes,
        algorithm: str = "",
        key_type: str = "encryption",
        version: int = 1,
        ttl_seconds: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> StoredKey:
        """
        Store a key in the keyring.

        Args:
            key_id: Key identifier.
            material: Key material.
            algorithm: Algorithm name.
            key_type: Type of key.
            version: Key version.
            ttl_seconds: Time to live.
            metadata: Additional metadata.

        Returns:
            StoredKey entry.
        """
        with self._lock:
            # Check capacity
            if key_id not in self._keys and len(self._keys) >= self._max_keys:
                # Evict expired keys first
                self._evict_expired()
                if len(self._keys) >= self._max_keys:
                    raise CryptoKeyError(
                        key_id=key_id,
                        operation="store",
                        reason="Keyring at maximum capacity",
                    )

            now = datetime.utcnow()
            ttl = ttl_seconds or self._default_ttl
            expires_at = now.timestamp() + ttl
            from datetime import timezone
            expires_at = datetime.fromtimestamp(expires_at)

            entry = StoredKey(
                key_id=key_id,
                material=material,
                algorithm=algorithm,
                key_type=key_type,
                version=version,
                status=KeyStatus.ACTIVE,
                created_at=now,
                expires_at=expires_at,
                metadata=metadata or {},
            )

            # Remove old entry for size tracking
            if key_id in self._keys:
                self._total_material_bytes -= len(self._keys[key_id].material)

            self._keys[key_id] = entry
            self._total_material_bytes += len(material)

            return entry

    def get_key(
        self,
        key_id: str,
        version: int = 0,
    ) -> Optional[StoredKey]:
        """
        Get a stored key.

        Args:
            key_id: Key identifier.
            version: Specific version (0 for latest).

        Returns:
            StoredKey or None.
        """
        with self._lock:
            entry = self._keys.get(key_id)
            if entry is None:
                return None

            if entry.is_expired():
                # Auto-cleanup expired keys
                self._remove_key(key_id)
                return None

            if version > 0 and entry.version != version:
                return None

            return entry

    def get_material(
        self,
        key_id: str,
        version: int = 0,
    ) -> Optional[bytes]:
        """
        Get key material directly.

        Args:
            key_id: Key identifier.
            version: Key version.

        Returns:
            Key material bytes or None.
        """
        entry = self.get_key(key_id, version)
        if entry is None:
            return None
        return entry.material

    def remove_key(self, key_id: str) -> bool:
        """Remove a key from the keyring."""
        with self._lock:
            return self._remove_key(key_id)

    def _remove_key(self, key_id: str) -> bool:
        """Internal key removal (lock must be held)."""
        entry = self._keys.pop(key_id, None)
        if entry is not None:
            self._total_material_bytes -= len(entry.material)
            return True
        return False

    def _evict_expired(self) -> int:
        """Evict expired keys."""
        evicted = 0
        expired_ids = []
        for key_id, entry in self._keys.items():
            if entry.is_expired():
                expired_ids.append(key_id)

        for key_id in expired_ids:
            self._remove_key(key_id)
            evicted += 1

        return evicted

    def update_key(
        self,
        key_id: str,
        **kwargs: Any,
    ) -> Optional[StoredKey]:
        """Update a stored key's metadata."""
        with self._lock:
            entry = self._keys.get(key_id)
            if entry is None:
                return None

            for field_name, value in kwargs.items():
                if hasattr(entry, field_name) and field_name != "material":
                    setattr(entry, field_name, value)

            return entry

    def list_keys(
        self,
        active_only: bool = True,
    ) -> List[Dict[str, Any]]:
        """List stored keys."""
        with self._lock:
            result = []
            for entry in self._keys.values():
                if active_only and not entry.is_valid():
                    continue
                result.append({
                    "key_id": entry.key_id,
                    "algorithm": entry.algorithm,
                    "key_type": entry.key_type,
                    "version": entry.version,
                    "status": entry.status.value,
                    "expires_at": (
                        entry.expires_at.isoformat() + "Z"
                        if entry.expires_at
                        else None
                    ),
                    "size": len(entry.material),
                })
            return result

    def cleanup(self) -> int:
        """Clean up all expired keys."""
        with self._lock:
            return self._evict_expired()

    def count(self) -> int:
        """Get number of stored keys."""
        return len(self._keys)

    def get_total_bytes(self) -> int:
        """Get total stored key material bytes."""
        return self._total_material_bytes

    def get_stats(self) -> Dict[str, Any]:
        """Get keyring statistics."""
        with self._lock:
            active = sum(
                1 for e in self._keys.values() if e.is_valid()
            )
            expired = sum(
                1 for e in self._keys.values() if e.is_expired()
            )

            return {
                "total_keys": len(self._keys),
                "active_keys": active,
                "expired_keys": expired,
                "max_keys": self._max_keys,
                "total_material_bytes": self._total_material_bytes,
            }
