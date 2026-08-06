"""Key management for ICYQuant Service Mesh.

Provides ``KeyManager`` for managing private keys, public keys,
session keys, and key rotation with zero plaintext exposure.
"""

from __future__ import annotations

import hashlib
import logging
import threading
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class KeyType(str):
    """Key types."""

    PRIVATE = "private"
    PUBLIC = "public"
    SESSION = "session"
    ROOT = "root"
    INTERMEDIATE = "intermediate"


class KeyRecord:
    """A key record."""

    def __init__(
        self,
        key_id: str,
        key_type: str,
        algorithm: str = "RSA-2048",
        key_data: str = "",
        owner: str = "",
        ttl_hours: int = 72,
    ) -> None:
        self.key_id = key_id
        self.key_type = key_type
        self.algorithm = algorithm
        self._key_data = key_data or f"key-data-{key_id}"
        self.owner = owner
        self.created_at = datetime.utcnow()
        self.expires_at = self.created_at + timedelta(hours=ttl_hours)
        self.rotated = False
        self.rotation_count = 0

    @property
    def is_expired(self) -> bool:
        return datetime.utcnow() > self.expires_at

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key_id": self.key_id,
            "key_type": self.key_type,
            "algorithm": self.algorithm,
            "owner": self.owner,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "is_expired": self.is_expired,
            "rotated": self.rotated,
            "rotation_count": self.rotation_count,
        }


class KeyManager:
    """Manages cryptographic keys."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._keys: Dict[str, KeyRecord] = {}
        self._rotation_interval_hours = 72
        self._create_count = 0
        self._rotate_count = 0

    def create_key(
        self,
        key_type: str = KeyType.PRIVATE,
        algorithm: str = "RSA-2048",
        owner: str = "",
        ttl_hours: int = 72,
    ) -> KeyRecord:
        """Create a new key."""
        with self._lock:
            self._create_count += 1
            key_id = f"key-{self._create_count:06d}"
        key = KeyRecord(
            key_id=key_id,
            key_type=key_type,
            algorithm=algorithm,
            owner=owner,
            ttl_hours=ttl_hours,
        )
        with self._lock:
            self._keys[key_id] = key
        logger.info("Key created: %s (type: %s)", key_id, key_type)
        return key

    def get_key(self, key_id: str) -> Optional[KeyRecord]:
        with self._lock:
            return self._keys.get(key_id)

    def rotate_key(self, key_id: str) -> Optional[KeyRecord]:
        """Rotate a key by creating a new one and marking old as rotated."""
        with self._lock:
            old_key = self._keys.get(key_id)
        if not old_key:
            return None
        new_key = self.create_key(
            key_type=old_key.key_type,
            algorithm=old_key.algorithm,
            owner=old_key.owner,
        )
        with self._lock:
            old_key.rotated = True
            old_key.rotation_count += 1
            self._rotate_count += 1
        logger.info("Key rotated: %s -> %s", key_id, new_key.key_id)
        return new_key

    def delete_key(self, key_id: str) -> bool:
        with self._lock:
            if key_id in self._keys:
                del self._keys[key_id]
                return True
            return False

    def list_keys(self, key_type: Optional[str] = None) -> List[KeyRecord]:
        with self._lock:
            keys = list(self._keys.values())
        if key_type:
            keys = [k for k in keys if k.key_type == key_type]
        return keys

    def cleanup_expired(self) -> int:
        with self._lock:
            expired = [kid for kid, k in self._keys.items() if k.is_expired]
            for kid in expired:
                del self._keys[kid]
        return len(expired)

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "total_keys": len(self._keys),
                "active_keys": sum(1 for k in self._keys.values() if not k.is_expired and not k.rotated),
                "create_count": self._create_count,
                "rotate_count": self._rotate_count,
            }
