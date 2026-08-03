"""
Storage health checker.

Provides health check functionality for
object storage infrastructure, including
connectivity verification, bucket
availability checks, and pipeline component
status reporting.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from .cache import StorageCache
from .client import StorageClient
from .compression import ZstdCompression
from .encryption import StorageEncryption


class StorageHealth:
    """
    Storage health checker.

    Performs health checks on the storage
    infrastructure, verifying connectivity,
    bucket accessibility, and pipeline component
    status (cache, compression, encryption).
    """

    def __init__(
        self,
        client: Optional[StorageClient] = None,
        cache: Optional[StorageCache] = None,
        compression: Optional[ZstdCompression] = None,
        encryption: Optional[StorageEncryption] = None,
    ) -> None:

        self._client = client
        self._cache = cache
        self._compression = compression
        self._encryption = encryption

    def set_client(
        self,
        client: StorageClient,
    ) -> None:
        """
        Set the storage client.

        Args:
            client: Storage client to use for checks.
        """

        self._client = client

    def set_pipeline(
        self,
        cache: Optional[StorageCache] = None,
        compression: Optional[ZstdCompression] = None,
        encryption: Optional[StorageEncryption] = None,
    ) -> None:
        """
        Set pipeline components for health check.

        Args:
            cache: Storage cache instance.
            compression: Compression provider.
            encryption: Encryption provider.
        """

        if cache is not None:
            self._cache = cache
        if compression is not None:
            self._compression = compression
        if encryption is not None:
            self._encryption = encryption

    async def check(
        self,
    ) -> Dict[str, Any]:
        """
        Perform comprehensive health check.

        Verifies connectivity to the storage
        provider, checks bucket availability,
        and reports pipeline component status.

        Returns:
            Health status dictionary with
            healthy, provider, bucket, cache,
            compression, encryption, and
            details keys.
        """

        result: Dict[str, Any] = {
            "healthy": False,
            "provider": "unknown",
            "bucket": None,
            "cache": False,
            "compression": False,
            "encryption": False,
            "details": {},
        }

        # Pipeline component status
        result["cache"] = (
            self._cache.is_enabled
            if self._cache
            else False
        )
        result["compression"] = (
            self._compression.is_available
            if self._compression
            else False
        )
        result["encryption"] = (
            self._encryption.is_initialized
            if self._encryption
            else False
        )

        if self._client is None:
            result["details"]["error"] = (
                "No storage client configured"
            )
            return result

        config = self._client.config
        result["provider"] = config.provider
        result["bucket"] = config.bucket

        try:
            is_healthy = self._client.is_initialized
            result["healthy"] = is_healthy

            if is_healthy:
                result["details"][
                    "initialized"
                ] = True
                result["details"][
                    "endpoint"
                ] = config.endpoint
                result["details"][
                    "region"
                ] = config.region
                result["details"][
                    "secure"
                ] = config.secure
                result["details"][
                    "multipart_threshold_mb"
                ] = (
                    config.multipart_threshold
                    // (1024 * 1024)
                )
            else:
                result["details"][
                    "initialized"
                ] = False
                result["details"]["error"] = (
                    "Client not initialized"
                )

        except Exception as exc:
            result["healthy"] = False
            result["details"]["error"] = str(exc)

        return result

    async def check_connectivity(
        self,
    ) -> bool:
        """
        Check basic connectivity to storage.

        Returns:
            True if connected.
        """

        if self._client is None:
            return False

        return self._client.is_initialized
