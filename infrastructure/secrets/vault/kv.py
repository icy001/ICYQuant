"""
Vault KV Secrets Engine v2.

Implements the KV v2 secrets engine for
reading, writing, listing, and managing
versioned secrets in HashiCorp Vault.

KV v2 features:
- Versioned secret storage
- Metadata management
- Secret deletion (soft and hard)
- Version history
- CAS (Check-And-Set) operations
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from .client import VaultClient
from .config import VaultConfig
from .exceptions import (
    VaultSecretNotFoundError,
    VaultWriteError,
)

logger = logging.getLogger(__name__)


class KVSecretsEngine:
    """
    KV v2 secrets engine client.

    Provides a high-level interface for
    interacting with Vault's KV v2 secrets
    engine, supporting all CRUD operations
    with versioning and metadata.

    Usage:
        client = VaultClient(config)
        kv = KVSecretsEngine(client, config)
        await kv.write("database/password", "secret123")
        value = await kv.read("database/password")
    """

    def __init__(
        self,
        client: VaultClient,
        config: VaultConfig,
    ) -> None:
        self._client = client
        self._config = config
        self._mount = config.mount
        self._version = config.mount_version

    # ── Read Operations ──

    async def read(
        self,
        key: str,
        version: Optional[int] = None,
    ) -> Optional[str]:
        """
        Read a secret value.

        Args:
            key: Secret key path.
            version: Specific version (None for latest).

        Returns:
            Secret value or None if not found.
        """
        path = self._read_path(key, version)

        try:
            result = await self._client.read(path)
            data = result.get("data", {})
            return data.get("data", {}).get("value")
        except VaultSecretNotFoundError:
            return None
        except Exception as e:
            logger.warning("KV read failed for %s: %s", key, e)
            return None

    async def read_full(
        self,
        key: str,
        version: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Read a secret with full metadata.

        Args:
            key: Secret key path.
            version: Specific version.

        Returns:
            Full response data dict.
        """
        path = self._read_path(key, version)

        try:
            result = await self._client.read(path)
            return result.get("data", {}).get("data")
        except VaultSecretNotFoundError:
            return None
        except Exception as e:
            logger.warning("KV read_full failed for %s: %s", key, e)
            return None

    # ── Write Operations ──

    async def write(
        self,
        key: str,
        value: Any,
        cas: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Write a secret value.

        Args:
            key: Secret key path.
            value: Secret value (any serializable type).
            cas: If set, perform Check-And-Set operation
                 requiring this version to be current.

        Returns:
            Write response with version info.
        """
        path = self._write_path(key)
        payload: Dict[str, Any] = {"data": {"value": value}}

        if cas is not None:
            payload["options"] = {"cas": cas}

        try:
            result = await self._client.write(path, payload=payload)
            logger.info("KV write: key=%s", key)
            return result
        except Exception as e:
            raise VaultWriteError(
                f"Failed to write secret '{key}': {e}",
                path=path,
            ) from e

    # ── Delete Operations ──

    async def delete(
        self,
        key: str,
    ) -> None:
        """
        Soft-delete the latest version of a secret.

        Args:
            key: Secret key path.
        """
        path = self._delete_path(key)
        await self._client.delete(path)
        logger.info("KV delete: key=%s", key)

    async def permanent_delete(
        self,
        key: str,
        version: int,
    ) -> None:
        """
        Permanently delete a specific secret version.

        Args:
            key: Secret key path.
            version: Version to permanently delete.
        """
        path = self._metadata_path(key)
        payload = {"versions": [version]}
        await self._client.write(f"{path}?permanent=true", payload=payload)
        logger.info("KV permanent delete: key=%s, version=%d", key, version)

    async def undelete(
        self,
        key: str,
        version: int,
    ) -> None:
        """
        Restore a soft-deleted secret version.

        Args:
            key: Secret key path.
            version: Version to restore.
        """
        path = self._metadata_path(key)
        payload = {"versions": [version]}
        await self._client.write(f"{path}?undelete=true", payload=payload)
        logger.info("KV undelete: key=%s, version=%d", key, version)

    # ── List Operations ──

    async def list(
        self,
        path_prefix: str = "",
    ) -> List[str]:
        """
        List secret keys at a path.

        Args:
            path_prefix: Path prefix to list under.

        Returns:
            List of key names.
        """
        list_path = f"/{self._mount}/metadata/{path_prefix}".rstrip("/")
        try:
            result = await self._client.list(list_path)
            return result.get("data", {}).get("keys", [])
        except Exception:
            return []

    # ── Metadata Operations ──

    async def get_metadata(
        self,
        key: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Get secret metadata without reading value.

        Args:
            key: Secret key path.

        Returns:
            Metadata dict with version info, or None.
        """
        path = self._metadata_path(key)
        try:
            result = await self._client.read(path)
            return result.get("data")
        except VaultSecretNotFoundError:
            return None
        except Exception as e:
            logger.warning("KV metadata failed for %s: %s", key, e)
            return None

    async def delete_metadata(
        self,
        key: str,
    ) -> None:
        """
        Delete all versions and metadata of a secret.

        Args:
            key: Secret key path.
        """
        path = self._metadata_path(key)
        await self._client.delete(path)
        logger.info("KV delete metadata: key=%s", key)

    async def configure_metadata(
        self,
        key: str,
        max_versions: Optional[int] = None,
        cas_required: Optional[bool] = None,
        delete_version_after: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Configure secret metadata settings.

        Args:
            key: Secret key path.
            max_versions: Max number of versions to keep.
            cas_required: Whether CAS is required.
            delete_version_after: Duration after which versions are auto-deleted.
        """
        path = self._metadata_path(key)
        payload: Dict[str, Any] = {}

        if max_versions is not None:
            payload["max_versions"] = max_versions
        if cas_required is not None:
            payload["cas_required"] = cas_required
        if delete_version_after is not None:
            payload["delete_version_after"] = delete_version_after

        return await self._client.write(path, payload=payload)

    # ── Path Helpers ──

    def _read_path(
        self,
        key: str,
        version: Optional[int] = None,
    ) -> str:
        """Build KV read API path."""
        # KV v2 uses /data/ for reads
        path = f"/{self._mount}/data/{key.lstrip('/')}"
        if version is not None:
            path += f"?version={version}"
        return path

    def _write_path(self, key: str) -> str:
        """Build KV write API path."""
        return f"/{self._mount}/data/{key.lstrip('/')}"

    def _delete_path(self, key: str) -> str:
        """Build KV delete API path."""
        return f"/{self._mount}/data/{key.lstrip('/')}"

    def _metadata_path(self, key: str) -> str:
        """Build KV metadata API path."""
        return f"/{self._mount}/metadata/{key.lstrip('/')}"
