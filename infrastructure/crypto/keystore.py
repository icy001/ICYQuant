"""
Key store for key lifecycle management.

Manages cryptographic key metadata,
version history, aliases, and lifecycle
state transitions including rotation,
disablement, and archival.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

from .constants import KeyStatus
from .exceptions import CryptoKeyError, CryptoKeyNotFoundError

logger = logging.getLogger(__name__)


@dataclass
class KeyMetadata:
    """
    Cryptographic key metadata.

    Tracks the lifecycle state and
    version history of a cryptographic key.

    Attributes:
        key_id: Unique key identifier.
        key_type: Type of key.
        algorithm: Algorithm name.
        status: Current key status.
        current_version: Current version number.
        created_at: Creation timestamp.
        updated_at: Last update timestamp.
        description: Key description.
        owner: Key owner/team.
        tags: Key tags.
    """

    key_id: str = ""
    key_type: str = "encryption"
    algorithm: str = ""
    status: KeyStatus = KeyStatus.ACTIVE
    current_version: int = 1
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    description: str = ""
    owner: str = ""
    tags: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key_id": self.key_id,
            "key_type": self.key_type,
            "algorithm": self.algorithm,
            "status": self.status.value,
            "current_version": self.current_version,
            "created_at": (
                self.created_at.isoformat() + "Z"
                if self.created_at
                else None
            ),
            "updated_at": (
                self.updated_at.isoformat() + "Z"
                if self.updated_at
                else None
            ),
            "description": self.description,
            "owner": self.owner,
            "tags": self.tags,
        }


@dataclass
class KeyVersion:
    """
    Key version history entry.

    Attributes:
        version: Version number.
        created_at: When this version was created.
        status: Version status.
        is_current: Whether this is the current version.
        metadata: Additional version metadata.
    """

    version: int = 1
    created_at: Optional[datetime] = None
    status: KeyStatus = KeyStatus.ACTIVE
    is_current: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "created_at": (
                self.created_at.isoformat() + "Z"
                if self.created_at
                else None
            ),
            "status": self.status.value,
            "is_current": self.is_current,
        }


class KeyStore:
    """
    Key metadata and version store.

    Manages cryptographic key metadata,
    version history, aliases, and lifecycle
    state transitions.

    Features:
    - Version history tracking
    - Alias management
    - State transitions (active -> rotating -> deprecated -> disabled)
    - Key tagging
    - Quarantine/archive support
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._keys: Dict[str, KeyMetadata] = {}
        self._versions: Dict[str, List[KeyVersion]] = {}
        self._aliases: Dict[str, str] = {}  # alias -> key_id

    def register_key(
        self,
        key_id: str,
        key_type: str = "encryption",
        algorithm: str = "",
        description: str = "",
        owner: str = "",
        tags: Optional[Dict[str, str]] = None,
    ) -> KeyMetadata:
        """
        Register a new key.

        Args:
            key_id: Unique key identifier.
            key_type: Type of key.
            algorithm: Algorithm name.
            description: Key description.
            owner: Key owner.
            tags: Key tags.

        Returns:
            KeyMetadata for the new key.
        """
        with self._lock:
            if key_id in self._keys:
                raise CryptoKeyError(
                    key_id=key_id,
                    operation="register",
                    reason="Key already exists",
                )

            now = datetime.utcnow()
            metadata = KeyMetadata(
                key_id=key_id,
                key_type=key_type,
                algorithm=algorithm,
                status=KeyStatus.ACTIVE,
                current_version=1,
                created_at=now,
                updated_at=now,
                description=description,
                owner=owner,
                tags=tags or {},
            )

            self._keys[key_id] = metadata

            # Create initial version
            self._versions[key_id] = [
                KeyVersion(
                    version=1,
                    created_at=now,
                    status=KeyStatus.ACTIVE,
                    is_current=True,
                )
            ]

            logger.info("Key registered: %s (%s)", key_id, key_type)
            return metadata

    def get_key(
        self,
        key_id: str,
    ) -> KeyMetadata:
        """Get key metadata by ID."""
        with self._lock:
            # Resolve alias
            resolved_id = self._aliases.get(key_id, key_id)

            if resolved_id not in self._keys:
                raise CryptoKeyNotFoundError(key_id=resolved_id)

            return self._keys[resolved_id]

    def update_key(
        self,
        key_id: str,
        **kwargs: Any,
    ) -> KeyMetadata:
        """Update key metadata."""
        with self._lock:
            key = self.get_key(key_id)

            for field_name, value in kwargs.items():
                if hasattr(key, field_name):
                    setattr(key, field_name, value)

            key.updated_at = datetime.utcnow()
            return key

    def rotate_key(
        self,
        key_id: str,
        new_version: int,
    ) -> KeyMetadata:
        """
        Record a key rotation.

        Args:
            key_id: Key being rotated.
            new_version: New version number.

        Returns:
            Updated KeyMetadata.
        """
        with self._lock:
            key = self.get_key(key_id)
            now = datetime.utcnow()

            # Mark old version as deprecated
            if key_id in self._versions:
                for v in self._versions[key_id]:
                    v.is_current = False
                    if v.status == KeyStatus.ACTIVE:
                        v.status = KeyStatus.DEPRECATED

                # Add new version
                self._versions[key_id].append(
                    KeyVersion(
                        version=new_version,
                        created_at=now,
                        status=KeyStatus.ACTIVE,
                        is_current=True,
                    )
                )

            key.current_version = new_version
            key.status = KeyStatus.ACTIVE
            key.updated_at = now

            logger.info(
                "Key rotated: %s v%d -> v%d",
                key_id, key.current_version, new_version,
            )
            return key

    def set_status(
        self,
        key_id: str,
        status: KeyStatus,
    ) -> KeyMetadata:
        """
        Set key lifecycle status.

        Args:
            key_id: Key to update.
            status: New status.

        Returns:
            Updated KeyMetadata.
        """
        with self._lock:
            key = self.get_key(key_id)
            key.status = status
            key.updated_at = datetime.utcnow()

            # Update version statuses
            if key_id in self._versions:
                for v in self._versions[key_id]:
                    v.status = status

            logger.info(
                "Key %s status set to: %s", key_id, status.value,
            )
            return key

    def disable_key(self, key_id: str) -> KeyMetadata:
        """Disable a key."""
        return self.set_status(key_id, KeyStatus.DISABLED)

    def archive_key(self, key_id: str) -> KeyMetadata:
        """Archive a key."""
        return self.set_status(key_id, KeyStatus.ARCHIVED)

    def add_alias(
        self,
        alias: str,
        key_id: str,
    ) -> None:
        """Add a key alias."""
        with self._lock:
            # Verify key exists
            self.get_key(key_id)
            self._aliases[alias] = key_id
            logger.info("Alias added: %s -> %s", alias, key_id)

    def remove_alias(self, alias: str) -> bool:
        """Remove a key alias."""
        with self._lock:
            return self._aliases.pop(alias, None) is not None

    def get_versions(
        self,
        key_id: str,
    ) -> List[KeyVersion]:
        """Get version history for a key."""
        with self._lock:
            self.get_key(key_id)  # Validate key exists
            return self._versions.get(key_id, [])

    def get_current_version(
        self,
        key_id: str,
    ) -> Optional[KeyVersion]:
        """Get the current version of a key."""
        versions = self.get_versions(key_id)
        for v in versions:
            if v.is_current:
                return v
        return None

    def list_keys(
        self,
        status: Optional[KeyStatus] = None,
        key_type: Optional[str] = None,
        prefix: str = "",
    ) -> List[KeyMetadata]:
        """List keys with optional filters."""
        with self._lock:
            result = []
            for key_id, key in self._keys.items():
                if prefix and not key_id.startswith(prefix):
                    continue
                if status and key.status != status:
                    continue
                if key_type and key.key_type != key_type:
                    continue
                result.append(key)
            return result

    def count(self) -> int:
        """Get number of stored keys."""
        return len(self._keys)

    def get_stats(self) -> Dict[str, Any]:
        """Get key store statistics."""
        with self._lock:
            status_counts: Dict[str, int] = {}
            for key in self._keys.values():
                s = key.status.value
                status_counts[s] = status_counts.get(s, 0) + 1

            return {
                "total_keys": len(self._keys),
                "total_aliases": len(self._aliases),
                "total_versions": sum(
                    len(v) for v in self._versions.values()
                ),
                "by_status": status_counts,
            }
