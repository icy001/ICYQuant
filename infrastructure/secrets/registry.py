"""
Secrets registry.

Manages the central registry of secrets,
providing thread-safe access to secret
items with version tracking and
namespace isolation.
"""

from __future__ import annotations

import threading
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

from .constants import SecretStatus
from .exceptions import SecretNotFoundError
from .models import SecretItem, SecretMetadata, SecretChangeEntry
from .utils import compute_checksum


class SecretsRegistry:
    """
    Central secrets registry.

    Manages the storage and retrieval of
    secret items with version tracking,
    namespace isolation, and thread-safe
    concurrent access.

    Usage:
        registry = SecretsRegistry()
        registry.register(SecretItem(key="db/password", value="secret123"))
        item = registry.get("db/password")
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        # Main storage: namespace -> key -> SecretItem
        self._secrets: Dict[str, Dict[str, SecretItem]] = {}
        # Metadata storage: namespace -> key -> SecretMetadata
        self._metadata: Dict[str, Dict[str, SecretMetadata]] = {}
        # Version history: namespace -> key -> List[SecretItem]
        self._history: Dict[str, Dict[str, List[SecretItem]]] = {}
        # Change log
        self._change_log: List[SecretChangeEntry] = []
        # Change log max size
        self._max_log_size = 10000
        # Change listeners
        self._listeners: List[Callable] = []

    # ── Registration ──

    def register(
        self,
        item: SecretItem,
    ) -> SecretItem:
        """
        Register or update a secret.

        Args:
            item: The secret item to register.

        Returns:
            The registered item (possibly with updated version).
        """
        with self._lock:
            namespace = item.namespace
            key = item.key

            self._ensure_namespace(namespace)

            # Compute checksum
            checksum = compute_checksum(item.value)

            # Check if secret already exists
            existing = self._secrets[namespace].get(key)
            if existing:
                # Version bump
                new_version = existing.version + 1
                item = SecretItem(
                    key=item.key,
                    value=item.value,
                    provider=item.provider,
                    version=new_version,
                    created_at=datetime.utcnow(),
                    expires_at=item.expires_at,
                    readonly=item.readonly,
                    category=item.category,
                    format=item.format,
                    namespace=item.namespace,
                    checksum=checksum,
                    metadata=item.metadata,
                )

                # Archive old version
                self._history.setdefault(namespace, {}).setdefault(key, []).append(existing)
            else:
                item = SecretItem(
                    key=item.key,
                    value=item.value,
                    provider=item.provider,
                    version=1,
                    created_at=item.created_at,
                    expires_at=item.expires_at,
                    readonly=item.readonly,
                    category=item.category,
                    format=item.format,
                    namespace=item.namespace,
                    checksum=checksum,
                    metadata=item.metadata,
                )

            # Store
            self._secrets[namespace][key] = item

            # Update metadata
            prev_metadata = self._metadata[namespace].get(key)
            self._metadata[namespace][key] = SecretMetadata(
                key=item.key,
                provider=item.provider,
                version=item.version,
                status=SecretStatus.ACTIVE,
                created_at=item.created_at,
                last_rotated_at=prev_metadata.last_rotated_at if prev_metadata else None,
                next_rotation_at=prev_metadata.next_rotation_at if prev_metadata else None,
                access_count=prev_metadata.access_count if prev_metadata else 0,
                namespace=item.namespace,
            )

            # Log change
            change = SecretChangeEntry(
                key=item.key,
                action="create" if not existing else "update",
                old_version=existing.version if existing else None,
                new_version=item.version,
                operator=item.metadata.get("operator", "system") if item.metadata else "system",
                reason=item.metadata.get("reason", "") if item.metadata else "",
            )
            self._log_change(change)

            # Notify listeners
            self._notify_listeners(change)

            return item

    def update(
        self,
        key: str,
        value: str,
        namespace: str = "default",
        **kwargs: Any,
    ) -> SecretItem:
        """
        Update an existing secret value.

        Args:
            key: The secret key.
            value: New value.
            namespace: Namespace.
            **kwargs: Additional SecretItem fields.

        Returns:
            Updated SecretItem.

        Raises:
            SecretNotFoundError: If key doesn't exist.
        """
        with self._lock:
            existing = self._secrets.get(namespace, {}).get(key)
            if not existing:
                raise SecretNotFoundError(key, namespace)

            if existing.readonly:
                raise PermissionError(
                    f"Cannot modify readonly secret: {namespace}/{key}"
                )

            checksum = compute_checksum(value)
            new_version = existing.version + 1

            item = SecretItem(
                key=key,
                value=value,
                provider=kwargs.get("provider", existing.provider),
                version=new_version,
                created_at=datetime.utcnow(),
                expires_at=kwargs.get("expires_at", existing.expires_at),
                readonly=kwargs.get("readonly", existing.readonly),
                category=kwargs.get("category", existing.category),
                format=kwargs.get("format", existing.format),
                namespace=namespace,
                checksum=checksum,
                metadata=kwargs.get("metadata", existing.metadata),
            )

            # Archive old version
            self._history[namespace][key].append(existing)

            # Store new version
            self._secrets[namespace][key] = item

            # Update metadata
            self._metadata[namespace][key] = SecretMetadata(
                key=key,
                provider=item.provider,
                version=item.version,
                status=SecretStatus.ACTIVE,
                created_at=item.created_at,
                last_rotated_at=self._metadata[namespace][key].last_rotated_at,
                next_rotation_at=self._metadata[namespace][key].next_rotation_at,
                access_count=self._metadata[namespace][key].access_count,
                namespace=namespace,
            )

            # Log change
            change = SecretChangeEntry(
                key=key,
                action="update",
                old_version=existing.version,
                new_version=new_version,
                operator=item.metadata.get("operator", "system") if item.metadata else "system",
                reason=item.metadata.get("reason", "") if item.metadata else "",
            )
            self._log_change(change)
            self._notify_listeners(change)

            return item

    # ── Retrieval ──

    def get(
        self,
        key: str,
        namespace: str = "default",
    ) -> SecretItem:
        """
        Get a secret item by key.

        Args:
            key: The secret key.
            namespace: Namespace.

        Returns:
            SecretItem.

        Raises:
            SecretNotFoundError: If not found.
        """
        with self._lock:
            item = self._secrets.get(namespace, {}).get(key)
            if not item:
                raise SecretNotFoundError(key, namespace)

            # Update access count
            if namespace in self._metadata and key in self._metadata[namespace]:
                meta = self._metadata[namespace][key]
                self._metadata[namespace][key] = SecretMetadata(
                    key=meta.key,
                    provider=meta.provider,
                    version=meta.version,
                    status=meta.status,
                    created_at=meta.created_at,
                    last_rotated_at=meta.last_rotated_at,
                    next_rotation_at=meta.next_rotation_at,
                    access_count=meta.access_count + 1,
                    namespace=meta.namespace,
                )

            return item

    def get_metadata(
        self,
        key: str,
        namespace: str = "default",
    ) -> Optional[SecretMetadata]:
        """
        Get secret metadata without exposing value.

        Args:
            key: The secret key.
            namespace: Namespace.

        Returns:
            SecretMetadata or None.
        """
        with self._lock:
            return self._metadata.get(namespace, {}).get(key)

    def exists(
        self,
        key: str,
        namespace: str = "default",
    ) -> bool:
        """Check if a secret exists."""
        with self._lock:
            return key in self._secrets.get(namespace, {})

    def list_secrets(
        self,
        namespace: str = "default",
    ) -> List[str]:
        """
        List all secret keys in a namespace.

        Args:
            namespace: Namespace.

        Returns:
            List of secret keys.
        """
        with self._lock:
            return list(self._secrets.get(namespace, {}).keys())

    def list_metadata(
        self,
        namespace: str = "default",
    ) -> List[SecretMetadata]:
        """
        List all secret metadata entries.

        Args:
            namespace: Namespace.

        Returns:
            List of SecretMetadata.
        """
        with self._lock:
            return list(self._metadata.get(namespace, {}).values())

    def get_history(
        self,
        key: str,
        namespace: str = "default",
    ) -> List[SecretItem]:
        """
        Get version history for a secret.

        Args:
            key: The secret key.
            namespace: Namespace.

        Returns:
            List of previous versions.
        """
        with self._lock:
            return list(self._history.get(namespace, {}).get(key, []))

    def get_version(
        self,
        key: str,
        version: int,
        namespace: str = "default",
    ) -> Optional[SecretItem]:
        """
        Get a specific version of a secret.

        Args:
            key: The secret key.
            version: Version number.
            namespace: Namespace.

        Returns:
            SecretItem or None if version not found.
        """
        with self._lock:
            # Check current
            current = self._secrets.get(namespace, {}).get(key)
            if current and current.version == version:
                return current

            # Check history
            for item in self._history.get(namespace, {}).get(key, []):
                if item.version == version:
                    return item

            return None

    # ── Deletion ──

    def delete(
        self,
        key: str,
        namespace: str = "default",
    ) -> bool:
        """
        Delete a secret.

        Args:
            key: The secret key.
            namespace: Namespace.

        Returns:
            True if deleted.
        """
        with self._lock:
            if key not in self._secrets.get(namespace, {}):
                return False

            # Archive to history before deleting
            old = self._secrets[namespace][key]
            self._history.setdefault(namespace, {}).setdefault(key, []).append(old)

            del self._secrets[namespace][key]
            if key in self._metadata.get(namespace, {}):
                self._metadata[namespace][key] = SecretMetadata(
                    key=key,
                    provider="",
                    version=old.version,
                    status=SecretStatus.DELETED,
                    created_at=old.created_at,
                    namespace=namespace,
                )

            # Log change
            change = SecretChangeEntry(
                key=key,
                action="delete",
                old_version=old.version,
                new_version=None,
                reason="Deleted",
            )
            self._log_change(change)
            self._notify_listeners(change)

            return True

    # ── Namespace Management ──

    def list_namespaces(self) -> List[str]:
        """List all namespaces."""
        with self._lock:
            return list(self._secrets.keys())

    def count(self, namespace: str = "default") -> int:
        """Count secrets in a namespace."""
        with self._lock:
            return len(self._secrets.get(namespace, {}))

    def total_count(self) -> int:
        """Count all secrets across all namespaces."""
        with self._lock:
            return sum(len(secrets) for secrets in self._secrets.values())

    # ── Change Log ──

    def get_change_log(
        self,
        limit: int = 100,
    ) -> List[SecretChangeEntry]:
        """
        Get recent change log entries.

        Args:
            limit: Maximum number of entries.

        Returns:
            List of change entries (most recent first).
        """
        with self._lock:
            return list(reversed(self._change_log[-limit:]))

    def add_listener(
        self,
        listener: Callable,
    ) -> None:
        """
        Add a change listener.

        Args:
            listener: Callable to invoke on changes.
        """
        with self._lock:
            self._listeners.append(listener)

    def remove_listener(
        self,
        listener: Callable,
    ) -> None:
        """Remove a change listener."""
        with self._lock:
            if listener in self._listeners:
                self._listeners.remove(listener)

    # ── Internal ──

    def _ensure_namespace(self, namespace: str) -> None:
        """Ensure a namespace exists."""
        if namespace not in self._secrets:
            self._secrets[namespace] = {}
        if namespace not in self._metadata:
            self._metadata[namespace] = {}
        if namespace not in self._history:
            self._history[namespace] = {}

    def _log_change(self, change: SecretChangeEntry) -> None:
        """Log a change entry."""
        self._change_log.append(change)
        if len(self._change_log) > self._max_log_size:
            self._change_log = self._change_log[-self._max_log_size:]

    def _notify_listeners(self, change: SecretChangeEntry) -> None:
        """Notify all change listeners."""
        for listener in self._listeners:
            try:
                if callable(listener):
                    listener(change)
            except Exception:
                pass

    def get_stats(self) -> Dict[str, Any]:
        """Get registry statistics."""
        with self._lock:
            return {
                "total_secrets": self.total_count(),
                "namespaces": list(self._secrets.keys()),
                "change_log_size": len(self._change_log),
                "listeners": len(self._listeners),
            }
