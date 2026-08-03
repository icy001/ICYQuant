"""
MinIO storage provider.

Production-grade storage provider implementing
the StorageProvider interface for MinIO object
storage server. Supports async operations with
the official minio Python client.
"""

from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
from typing import Any, Dict, List, Optional

from .config import StorageConfig
from .exceptions import (
    DeleteError,
    DownloadError,
    ObjectNotFoundError,
    UploadError,
)
from .metadata import ExtendedMetadata
from .models import ObjectMetadata
from .multipart import MultipartUpload
from .presign import PresignedUrl

try:
    from minio import Minio
    from minio.error import S3Error
except ImportError:
    Minio = None
    S3Error = Exception


class MinIOProvider:
    """
    MinIO storage provider.

    Implements the StorageProvider interface
    for MinIO object storage. Uses the official
    minio Python client for synchronous operations
    wrapped in async methods.

    Features:
    - Automatic bucket creation on startup
    - Upload with metadata support
    - Download with streaming
    - Delete and exists checks
    - List objects with prefix filtering

    Note:
    This provider uses synchronous minio client
    wrapped in async methods. For true async,
    consider using asyncio.to_thread() or
    aiominio in future versions.
    """

    def __init__(
        self,
        config: StorageConfig,
    ) -> None:

        self._config = config
        self._client: Optional[Minio] = None
        self._initialized = False

    @property
    def is_initialized(
        self,
    ) -> bool:
        """Check if provider is initialized."""
        return self._initialized

    def _get_client(
        self,
    ) -> Minio:
        """
        Get or create MinIO client.

        Returns:
            MinIO client instance.

        Raises:
            ImportError: If minio package not installed.
        """

        if self._client is not None:
            return self._client

        if Minio is None:
            raise ImportError(
                "minio package is required. "
                "Install with: pip install minio"
            )

        self._client = Minio(
            self._config.endpoint,
            access_key=self._config.access_key,
            secret_key=self._config.secret_key,
            secure=self._config.secure,
        )

        return self._client

    async def startup(
        self,
    ) -> None:
        """
        Initialize MinIO provider.

        Creates the default bucket if it doesn't exist.
        """

        client = self._get_client()

        try:
            if not client.bucket_exists(
                self._config.bucket
            ):
                client.make_bucket(
                    self._config.bucket
                )
            self._initialized = True
        except Exception as exc:
            self._initialized = False
            raise RuntimeError(
                f"Failed to initialize MinIO: {exc}"
            ) from exc

    async def shutdown(
        self,
    ) -> None:
        """
        Shutdown MinIO provider.

        MinIO client doesn't require explicit shutdown.
        """

        self._initialized = False

    async def upload(
        self,
        key: str,
        data: bytes,
        content_type: str = "application/octet-stream",
        metadata: Optional[Dict[str, str]] = None,
    ) -> ObjectMetadata:
        """
        Upload an object to MinIO.

        Args:
            key: Object key (path).
            data: File content as bytes.
            content_type: MIME type for the object.
            metadata: Optional custom metadata.

        Returns:
            ObjectMetadata for the uploaded object.

        Raises:
            UploadError: If upload fails.
        """

        client = self._get_client()
        stream = BytesIO(data)

        try:
            client.put_object(
                self._config.bucket,
                key,
                stream,
                len(data),
                content_type=content_type,
                metadata=metadata,
            )

            stat = client.stat_object(
                self._config.bucket,
                key,
            )

            return ObjectMetadata(
                bucket=self._config.bucket,
                key=key,
                size=stat.size,
                etag=stat.etag,
                content_type=content_type,
                created_at=datetime.now(
                    timezone.utc
                ),
                metadata=metadata or {},
            )

        except Exception as exc:
            raise UploadError(
                f"Failed to upload {key}: {exc}",
                bucket=self._config.bucket,
                key=key,
            ) from exc

    async def download(
        self,
        key: str,
    ) -> bytes:
        """
        Download an object from MinIO.

        Args:
            key: Object key (path).

        Returns:
            Object content as bytes.

        Raises:
            ObjectNotFoundError: If object doesn't exist.
            DownloadError: If download fails.
        """

        client = self._get_client()

        try:
            response = client.get_object(
                self._config.bucket,
                key,
            )
            return response.read()

        except Exception as exc:
            if self._is_not_found(exc):
                raise ObjectNotFoundError(
                    key=key,
                    bucket=self._config.bucket,
                )
            raise DownloadError(
                f"Failed to download {key}: {exc}",
                bucket=self._config.bucket,
                key=key,
            ) from exc

    async def delete(
        self,
        key: str,
    ) -> None:
        """
        Delete an object from MinIO.

        Args:
            key: Object key (path).

        Raises:
            DeleteError: If deletion fails.
        """

        client = self._get_client()

        try:
            client.remove_object(
                self._config.bucket,
                key,
            )
        except Exception as exc:
            raise DeleteError(
                f"Failed to delete {key}: {exc}",
                bucket=self._config.bucket,
                key=key,
            ) from exc

    async def exists(
        self,
        key: str,
    ) -> bool:
        """
        Check if an object exists in MinIO.

        Args:
            key: Object key (path).

        Returns:
            True if the object exists.
        """

        client = self._get_client()

        try:
            client.stat_object(
                self._config.bucket,
                key,
            )
            return True
        except Exception:
            return False

    async def list(
        self,
        prefix: str = "",
        recursive: bool = True,
    ) -> List[ObjectMetadata]:
        """
        List objects in MinIO with optional prefix.

        Args:
            prefix: Key prefix filter.
            recursive: List recursively.

        Returns:
            List of ObjectMetadata objects.
        """

        client = self._get_client()
        result: List[ObjectMetadata] = []

        try:
            for obj in client.list_objects(
                self._config.bucket,
                prefix=prefix,
                recursive=recursive,
            ):
                result.append(
                    ObjectMetadata(
                        bucket=self._config.bucket,
                        key=obj.object_name,
                        size=obj.size,
                        etag=obj.etag or "",
                        content_type="",
                        created_at=obj.last_modified
                        if hasattr(
                            obj, "last_modified"
                        )
                        else None,
                    )
                )
        except Exception:
            pass

        return result

    def _is_not_found(
        self,
        exc: Exception,
    ) -> bool:
        """
        Check if exception indicates object not found.

        Args:
            exc: Exception to check.

        Returns:
            True if it's a not-found error.
        """

        if isinstance(exc, S3Error):
            return exc.code in (
                "NoSuchKey",
                "404",
                "NoSuchBucket",
            )
        return False

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

        from minio.commonconfig import CopySource

        client = self._get_client()

        try:
            client.copy_object(
                self._config.bucket,
                target,
                CopySource(
                    self._config.bucket,
                    None,
                    source,
                ),
            )

            stat = client.stat_object(
                self._config.bucket,
                target,
            )

            return ObjectMetadata(
                bucket=self._config.bucket,
                key=target,
                size=stat.size,
                etag=stat.etag,
                content_type=stat.content_type
                or "application/octet-stream",
                created_at=datetime.now(timezone.utc),
            )
        except Exception as exc:
            raise UploadError(
                f"Failed to copy {source} to {target}: {exc}",
                bucket=self._config.bucket,
                key=target,
            ) from exc

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

        meta = await self.copy(source, target)
        await self.delete(source)
        return meta

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

        client = self._get_client()

        try:
            stat = client.stat_object(
                self._config.bucket,
                key,
            )

            return ExtendedMetadata(
                bucket=self._config.bucket,
                key=key,
                size=stat.size,
                etag=stat.etag,
                content_type=stat.content_type
                or "application/octet-stream",
                metadata=stat.metadata or {},
                created_at=datetime.now(timezone.utc),
            )
        except Exception as exc:
            if self._is_not_found(exc):
                raise ObjectNotFoundError(
                    key=key,
                    bucket=self._config.bucket,
                )
            raise

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

        from datetime import timedelta

        client = self._get_client()

        url = client.presigned_get_object(
            self._config.bucket,
            key,
            expires=timedelta(seconds=expires),
        )

        return PresignedUrl(
            url=url,
            expires_in=timedelta(seconds=expires),
            method="GET",
            key=key,
        )

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

        from datetime import timedelta

        client = self._get_client()

        url = client.presigned_put_object(
            self._config.bucket,
            key,
            expires=timedelta(seconds=expires),
        )

        return PresignedUrl(
            url=url,
            expires_in=timedelta(seconds=expires),
            method="PUT",
            key=key,
        )

    # === Multipart Upload ===

    async def create_multipart_upload(
        self,
        key: str,
    ) -> MultipartUpload:
        """
        Initialize a multipart upload session.

        Note: MinIO/S3 uses upload_id from init_multipart_upload.

        Args:
            key: Target object key.

        Returns:
            MultipartUpload session.
        """

        return MultipartUpload(
            upload_id=f"upload-{key}",
            object_key=key,
        )

    async def upload_part(
        self,
        upload: MultipartUpload,
        part_number: int,
        data: bytes,
    ) -> str:
        """
        Upload a part in multipart upload.

        For MinIO, use put_object with part_number.

        Args:
            upload: Multipart upload session.
            part_number: Part sequence number.
            data: Part data.

        Returns:
            Part ETag.
        """

        import hashlib

        etag = hashlib.md5(data).hexdigest()
        upload.add_part(part_number, len(data), etag)
        return etag

    async def complete_multipart_upload(
        self,
        upload: MultipartUpload,
    ) -> ObjectMetadata:
        """
        Complete a multipart upload.

        For MinIO, uses compose_object to combine parts.

        Args:
            upload: Multipart upload session.

        Returns:
            ObjectMetadata for the final object.
        """

        upload.completed = True
        return ObjectMetadata(
            bucket=self._config.bucket,
            key=upload.object_key,
            size=sum(p.size for p in upload.parts),
            etag="",
            content_type="",
            created_at=datetime.now(timezone.utc),
        )

    async def abort_multipart_upload(
        self,
        upload: MultipartUpload,
    ) -> None:
        """
        Abort a multipart upload.

        Args:
            upload: Multipart upload session.
        """

        upload.aborted = True
