"""
Storage client.

Provides a provider-independent client for
object storage operations, serving as the main
entry point for business modules to interact
with the storage infrastructure. Includes
auto-provider factory based on configuration.
"""

from __future__ import annotations

from typing import (
    BinaryIO,
    Dict,
    List,
    Optional,
    Type,
)

from .config import StorageConfig
from .exceptions import (
    StorageConnectionError,
    StorageError,
)
from .local import LocalStorageProvider
from .minio import MinIOProvider
from .models import (
    ObjectMetadata,
)
from .provider import StorageProvider
from .s3 import S3Provider
from .serializer import (
    ObjectSerializer,
    PathSerializer,
)


# Provider mapping for factory
_PROVIDER_MAP: Dict[
    str, Type[StorageProvider]
] = {
    "minio": MinIOProvider,
    "s3": S3Provider,
    "local": LocalStorageProvider,
}


class StorageClient:
    """
    Provider-independent storage client.

    Provides a unified interface for object
    storage operations, delegating to the
    configured provider implementation.

    Features:
    - Auto-provider factory from config
    - Automatic path normalization
    - Serialization/deserialization
    - JSON upload/download convenience methods
    """

    def __init__(
        self,
        config: StorageConfig,
        provider: Optional[StorageProvider] = None,
    ) -> None:

        self._config = config
        self._provider: Optional[StorageProvider] = provider
        self._initialized = False

        # Auto-create provider from config
        if provider is None:
            self._provider = self._create_provider(
                config
            )

    @staticmethod
    def _create_provider(
        config: StorageConfig,
    ) -> StorageProvider:
        """
        Create storage provider from config.

        Uses the provider mapping to instantiate
        the correct provider implementation.

        Args:
            config: Storage configuration.

        Returns:
            Initialized storage provider.

        Raises:
            ValueError: If provider is not supported.
        """

        provider_class = _PROVIDER_MAP.get(
            config.provider
        )

        if provider_class is None:
            supported = list(_PROVIDER_MAP.keys())
            raise ValueError(
                f"Unsupported provider: {config.provider}. "
                f"Supported: {supported}"
            )

        return provider_class(config)

    @classmethod
    def from_provider(
        cls,
        provider: str,
        endpoint: str = "",
        bucket: str = "",
        **kwargs: object,
    ) -> StorageClient:
        """
        Create client from provider name.

        Convenience factory method for quick
        client creation.

        Args:
            provider: Provider name (minio, s3, local).
            endpoint: Provider endpoint.
            bucket: Bucket name.
            **kwargs: Additional config options.

        Returns:
            StorageClient instance.
        """

        config = StorageConfig(
            provider=provider,
            endpoint=endpoint,
            bucket=bucket,
            **kwargs,
        )

        return cls(config)

    @property
    def config(
        self,
    ) -> StorageConfig:
        """
        Get storage configuration.

        Returns:
            Storage configuration.
        """

        return self._config

    @property
    def provider(
        self,
    ) -> StorageProvider:
        """
        Get the storage provider.

        Returns:
            Initialized storage provider.

        Raises:
            StorageConnectionError: If provider not set.
        """

        if self._provider is None:
            raise StorageConnectionError(
                "Storage provider not set."
            )

        return self._provider

    @property
    def is_initialized(
        self,
    ) -> bool:
        """
        Check if client is initialized.

        Returns:
            True if provider is initialized.
        """

        return self._initialized

    def set_provider(
        self,
        provider: StorageProvider,
    ) -> None:
        """
        Set or replace the storage provider.

        Args:
            provider: Storage provider implementation.
        """

        self._provider = provider

    async def startup(
        self,
    ) -> None:
        """
        Initialize storage client.

        Starts the storage provider connection.

        Raises:
            StorageConnectionError: If connection fails.
        """

        if self._provider is None:
            raise StorageConnectionError(
                "No storage provider configured."
            )

        try:
            await self._provider.startup()
            self._initialized = True
        except Exception as exc:
            self._initialized = False
            raise StorageConnectionError(
                f"Failed to connect to storage: {exc}"
            ) from exc

    async def shutdown(
        self,
    ) -> None:
        """
        Shutdown storage client.

        Gracefully closes the provider connection.
        """

        if self._provider:
            await self._provider.shutdown()
            self._initialized = False

    async def upload(
        self,
        key: str,
        data: bytes | BinaryIO,
        content_type: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
    ) -> ObjectMetadata:
        """
        Upload an object to storage.

        Args:
            key: Object key (path). Will be normalized.
            data: File content as bytes or file object.
            content_type: MIME type.
            metadata: Custom metadata.

        Returns:
            ObjectMetadata for the uploaded object.
        """

        normalized_key = (
            PathSerializer.normalize(key)
        )

        if isinstance(data, (bytes, bytearray)):
            byte_data = bytes(data)
        elif hasattr(data, "read"):
            byte_data = data.read()
        else:
            byte_data = bytes(data)

        return await self.provider.upload(
            key=normalized_key,
            data=byte_data,
            content_type=content_type
            or "application/octet-stream",
            metadata=metadata,
        )

    async def upload_json(
        self,
        key: str,
        data: object,
        metadata: Optional[Dict[str, str]] = None,
    ) -> ObjectMetadata:
        """
        Upload a JSON-serializable object.

        Args:
            key: Object key (path).
            data: JSON-serializable object.
            metadata: Custom metadata.

        Returns:
            ObjectMetadata for the uploaded object.
        """

        json_bytes = ObjectSerializer.to_json(data)

        return await self.upload(
            key=key,
            data=json_bytes,
            content_type="application/json",
            metadata=metadata,
        )

    async def download(
        self,
        key: str,
    ) -> bytes:
        """
        Download an object from storage.

        Args:
            key: Object key (path).

        Returns:
            Object content as bytes.
        """

        normalized_key = (
            PathSerializer.normalize(key)
        )

        return await self.provider.download(
            key=normalized_key,
        )

    async def download_json(
        self,
        key: str,
    ) -> object:
        """
        Download and deserialize a JSON object.

        Args:
            key: Object key (path).

        Returns:
            Deserialized Python object.
        """

        data = await self.download(key=key)

        return ObjectSerializer.from_json(data)

    async def delete(
        self,
        key: str,
    ) -> None:
        """
        Delete an object from storage.

        Args:
            key: Object key (path).
        """

        normalized_key = (
            PathSerializer.normalize(key)
        )

        await self.provider.delete(
            key=normalized_key,
        )

    async def exists(
        self,
        key: str,
    ) -> bool:
        """
        Check if an object exists.

        Args:
            key: Object key (path).

        Returns:
            True if object exists.
        """

        normalized_key = (
            PathSerializer.normalize(key)
        )

        return await self.provider.exists(
            key=normalized_key,
        )

    async def list_objects(
        self,
        prefix: str = "",
    ) -> List[ObjectMetadata]:
        """
        List objects with optional prefix filter.

        Args:
            prefix: Key prefix filter.

        Returns:
            List of ObjectMetadata objects.
        """

        normalized_prefix = (
            PathSerializer.normalize(prefix)
            if prefix
            else ""
        )

        return await self.provider.list(
            prefix=normalized_prefix,
        )

    @staticmethod
    def supported_providers() -> List[str]:
        """
        List supported provider names.

        Returns:
            List of provider names.
        """

        return list(_PROVIDER_MAP.keys())
