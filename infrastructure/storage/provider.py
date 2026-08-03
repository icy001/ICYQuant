"""
Storage provider abstraction.

Defines the Provider interface (Protocol)
for object storage, enabling seamless switching
between MinIO, AWS S3, Azure Blob, GCS, and
local filesystem implementations.

Includes advanced operations for copy, move,
presigned URLs, and extended metadata.
"""

from __future__ import annotations

from typing import (
    Dict,
    List,
    Optional,
    Protocol,
    runtime_checkable,
)

from .metadata import ExtendedMetadata
from .models import ObjectMetadata
from .multipart import MultipartUpload
from .presign import PresignedUrl


@runtime_checkable
class StorageProvider(Protocol):
    """
    Storage provider protocol.

    Defines the minimal interface that all
    storage provider implementations must
    satisfy. Enables dependency injection
    and runtime provider selection.

    Providers use bucket from config internally.
    For multi-bucket support, create separate
    client instances with different configs.

    Implementations:
    - MinIOProvider
    - S3Provider
    - AzureBlobProvider (future)
    - GCSProvider (future)
    - LocalStorageProvider (testing)
    """

    # === Core Operations ===

    async def startup(
        self,
    ) -> None:
        """
        Initialize provider connection.
        """

        ...

    async def shutdown(
        self,
    ) -> None:
        """
        Close provider connection.
        """

        ...

    async def upload(
        self,
        key: str,
        data: bytes,
        content_type: str = "application/octet-stream",
        metadata: Optional[Dict[str, str]] = None,
    ) -> ObjectMetadata:
        """
        Upload an object to storage.

        Args:
            key: Object key (path).
            data: File content as bytes.
            content_type: MIME type for the object.
            metadata: Optional custom metadata.

        Returns:
            ObjectMetadata for the uploaded object.
        """

        ...

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

        ...

    async def delete(
        self,
        key: str,
    ) -> None:
        """
        Delete an object from storage.

        Args:
            key: Object key (path).
        """

        ...

    async def exists(
        self,
        key: str,
    ) -> bool:
        """
        Check if an object exists.

        Args:
            key: Object key (path).

        Returns:
            True if the object exists.
        """

        ...

    async def list(
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

        ...

    # === Advanced Operations ===

    async def copy(
        self,
        source: str,
        target: str,
    ) -> ObjectMetadata:
        """
        Copy an object within the same bucket.

        Args:
            source: Source object key.
            target: Target object key.

        Returns:
            ObjectMetadata for the copied object.
        """

        ...

    async def move(
        self,
        source: str,
        target: str,
    ) -> ObjectMetadata:
        """
        Move an object within the same bucket.

        Args:
            source: Source object key.
            target: Target object key.

        Returns:
            ObjectMetadata for the moved object.
        """

        ...

    async def get_extended_metadata(
        self,
        key: str,
    ) -> ExtendedMetadata:
        """
        Get extended object metadata.

        Args:
            key: Object key (path).

        Returns:
            ExtendedMetadata with full object information.
        """

        ...

    async def presign_download(
        self,
        key: str,
        expires: int = 3600,
    ) -> PresignedUrl:
        """
        Generate a presigned download URL.

        Args:
            key: Object key (path).
            expires: URL expiration in seconds.

        Returns:
            PresignedUrl for downloading.
        """

        ...

    async def presign_upload(
        self,
        key: str,
        expires: int = 3600,
    ) -> PresignedUrl:
        """
        Generate a presigned upload URL.

        Args:
            key: Object key (path).
            expires: URL expiration in seconds.

        Returns:
            PresignedUrl for uploading.
        """

        ...

    # === Multipart Upload ===

    async def create_multipart_upload(
        self,
        key: str,
    ) -> MultipartUpload:
        """
        Initialize a multipart upload session.

        Args:
            key: Target object key.

        Returns:
            MultipartUpload session.
        """

        ...

    async def upload_part(
        self,
        upload: MultipartUpload,
        part_number: int,
        data: bytes,
    ) -> str:
        """
        Upload a part in multipart upload.

        Args:
            upload: Multipart upload session.
            part_number: Part sequence number (1-based).
            data: Part data.

        Returns:
            Part ETag.
        """

        ...

    async def complete_multipart_upload(
        self,
        upload: MultipartUpload,
    ) -> ObjectMetadata:
        """
        Complete a multipart upload.

        Args:
            upload: Multipart upload session.

        Returns:
            ObjectMetadata for the final object.
        """

        ...

    async def abort_multipart_upload(
        self,
        upload: MultipartUpload,
    ) -> None:
        """
        Abort a multipart upload.

        Args:
            upload: Multipart upload session.
        """

        ...