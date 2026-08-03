"""
Amazon S3 storage provider.

Production-grade storage provider implementing
the StorageProvider interface for Amazon S3
cloud object storage.
"""

from __future__ import annotations

from datetime import datetime, timezone
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
    import boto3
    from botocore.exceptions import (
        ClientError,
    )
except ImportError:
    boto3 = None
    ClientError = Exception


class S3Provider:
    """
    Amazon S3 storage provider.

    Implements the StorageProvider interface
    for Amazon S3 using boto3 SDK. Supports
    all standard S3 operations with automatic
    bucket creation and metadata tracking.

    Features:
    - Automatic bucket creation on startup
    - Upload with metadata and content type
    - Download with streaming support
    - Delete and exists checks
    - List objects with prefix filtering
    """

    def __init__(
        self,
        config: StorageConfig,
    ) -> None:

        self._config = config
        self._client: Optional[Any] = None
        self._initialized = False

    @property
    def is_initialized(
        self,
    ) -> bool:
        """Check if provider is initialized."""
        return self._initialized

    def _get_client(
        self,
    ) -> Any:
        """
        Get or create S3 client.

        Returns:
            boto3 S3 client instance.

        Raises:
            ImportError: If boto3 not installed.
        """

        if self._client is not None:
            return self._client

        if boto3 is None:
            raise ImportError(
                "boto3 package is required. "
                "Install with: pip install boto3"
            )

        self._client = boto3.client(
            "s3",
            endpoint_url=(
                f"{'https' if self._config.secure else 'http'}://"
                f"{self._config.endpoint}"
            ),
            aws_access_key_id=(
                self._config.access_key
            ),
            aws_secret_access_key=(
                self._config.secret_key
            ),
            region_name=(
                self._config.region or "us-east-1"
            ),
        )

        return self._client

    async def startup(
        self,
    ) -> None:
        """
        Initialize S3 provider.

        Creates the default bucket if it doesn't exist.
        """

        client = self._get_client()

        try:
            client.head_bucket(
                Bucket=self._config.bucket
            )
        except ClientError as exc:
            error_code = exc.response.get(
                "Error", {}
            ).get("Code", "")

            if error_code in (
                "404",
                "NoSuchBucket",
            ):
                try:
                    create_kwargs = {
                        "Bucket": self._config.bucket
                    }
                    if self._config.region:
                        create_kwargs[
                            "CreateBucketConfiguration"
                        ] = {
                            "LocationConstraint": (
                                self._config.region
                            )
                        }
                    client.create_bucket(
                        **create_kwargs
                    )
                except Exception as create_exc:
                    raise RuntimeError(
                        f"Failed to create bucket: {create_exc}"
                    ) from create_exc
            else:
                raise RuntimeError(
                    f"S3 bucket check failed: {exc}"
                ) from exc

        self._initialized = True

    async def shutdown(
        self,
    ) -> None:
        """
        Shutdown S3 provider.

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
        Upload an object to S3.

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

        try:
            put_kwargs: Dict[str, Any] = {
                "Bucket": self._config.bucket,
                "Key": key,
                "Body": data,
                "ContentType": content_type,
            }

            if metadata:
                put_kwargs["Metadata"] = metadata

            client.put_object(**put_kwargs)

            response = client.head_object(
                Bucket=self._config.bucket,
                Key=key,
            )

            return ObjectMetadata(
                bucket=self._config.bucket,
                key=key,
                size=response.get(
                    "ContentLength", len(data)
                ),
                etag=response.get(
                    "ETag", ""
                ).strip('"'),
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
        Download an object from S3.

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
                Bucket=self._config.bucket,
                Key=key,
            )
            return response["Body"].read()

        except ClientError as exc:
            if exc.response.get(
                "Error", {}
            ).get("Code") in (
                "404",
                "NoSuchKey",
            ):
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
        Delete an object from S3.

        Args:
            key: Object key (path).

        Raises:
            DeleteError: If deletion fails.
        """

        client = self._get_client()

        try:
            client.delete_object(
                Bucket=self._config.bucket,
                Key=key,
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
        Check if an object exists in S3.

        Args:
            key: Object key (path).

        Returns:
            True if the object exists.
        """

        client = self._get_client()

        try:
            client.head_object(
                Bucket=self._config.bucket,
                Key=key,
            )
            return True
        except ClientError:
            return False

    async def list(
        self,
        prefix: str = "",
        max_keys: int = 1000,
    ) -> List[ObjectMetadata]:
        """
        List objects in S3 with optional prefix.

        Args:
            prefix: Key prefix filter.
            max_keys: Maximum number of keys.

        Returns:
            List of ObjectMetadata objects.
        """

        client = self._get_client()
        result: List[ObjectMetadata] = []

        try:
            paginator = client.get_paginator(
                "list_objects_v2"
            )

            for page in paginator.paginate(
                Bucket=self._config.bucket,
                Prefix=prefix,
                MaxKeys=max_keys,
            ):
                for obj in page.get(
                    "Contents", []
                ):
                    result.append(
                        ObjectMetadata(
                            bucket=(
                                self._config.bucket
                            ),
                            key=obj.get(
                                "Key", ""
                            ),
                            size=obj.get(
                                "Size", 0
                            ),
                            etag=(
                                obj.get(
                                    "ETag", ""
                                ).strip('"')
                            ),
                            content_type="",
                            created_at=(
                                obj.get(
                                    "LastModified"
                                )
                            ),
                        )
                    )
        except Exception:
            pass

        return result

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

        client = self._get_client()

        try:
            client.copy_object(
                Bucket=self._config.bucket,
                Key=target,
                CopySource={
                    "Bucket": self._config.bucket,
                    "Key": source,
                },
            )

            response = client.head_object(
                Bucket=self._config.bucket,
                Key=target,
            )

            return ObjectMetadata(
                bucket=self._config.bucket,
                key=target,
                size=response.get("ContentLength", 0),
                etag=response.get("ETag", "").strip('"'),
                content_type=response.get(
                    "ContentType",
                    "application/octet-stream",
                ),
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
            response = client.head_object(
                Bucket=self._config.bucket,
                Key=key,
            )

            return ExtendedMetadata(
                bucket=self._config.bucket,
                key=key,
                size=response.get("ContentLength", 0),
                etag=response.get("ETag", "").strip('"'),
                content_type=response.get(
                    "ContentType",
                    "application/octet-stream",
                ),
                metadata=response.get("Metadata", {}),
                created_at=response.get("LastModified"),
            )
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in (
                "404",
                "NoSuchKey",
            ):
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

        url = client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": self._config.bucket,
                "Key": key,
            },
            ExpiresIn=expires,
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

        url = client.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": self._config.bucket,
                "Key": key,
            },
            ExpiresIn=expires,
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

        Args:
            key: Target object key.

        Returns:
            MultipartUpload session.
        """

        client = self._get_client()

        try:
            response = client.create_multipart_upload(
                Bucket=self._config.bucket,
                Key=key,
            )

            return MultipartUpload(
                upload_id=response["UploadId"],
                object_key=key,
            )
        except Exception as exc:
            raise UploadError(
                f"Failed to create multipart upload: {exc}",
                bucket=self._config.bucket,
                key=key,
            ) from exc

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
            part_number: Part sequence number.
            data: Part data.

        Returns:
            Part ETag.
        """

        client = self._get_client()

        try:
            response = client.upload_part(
                Bucket=self._config.bucket,
                Key=upload.object_key,
                UploadId=upload.upload_id,
                PartNumber=part_number,
                Body=data,
            )

            etag = response["ETag"]
            upload.add_part(part_number, len(data), etag)
            return etag
        except Exception as exc:
            raise UploadError(
                f"Failed to upload part {part_number}: {exc}",
                bucket=self._config.bucket,
                key=upload.object_key,
            ) from exc

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

        client = self._get_client()

        try:
            parts = [
                {
                    "PartNumber": p.part_number,
                    "ETag": p.etag,
                }
                for p in upload.parts
            ]

            client.complete_multipart_upload(
                Bucket=self._config.bucket,
                Key=upload.object_key,
                UploadId=upload.upload_id,
                MultipartUpload={"Parts": parts},
            )

            upload.completed = True

            return ObjectMetadata(
                bucket=self._config.bucket,
                key=upload.object_key,
                size=sum(p.size for p in upload.parts),
                etag="",
                content_type="",
                created_at=datetime.now(timezone.utc),
            )
        except Exception as exc:
            raise UploadError(
                f"Failed to complete multipart upload: {exc}",
                bucket=self._config.bucket,
                key=upload.object_key,
            ) from exc

    async def abort_multipart_upload(
        self,
        upload: MultipartUpload,
    ) -> None:
        """
        Abort a multipart upload.

        Args:
            upload: Multipart upload session.
        """

        client = self._get_client()

        try:
            client.abort_multipart_upload(
                Bucket=self._config.bucket,
                Key=upload.object_key,
                UploadId=upload.upload_id,
            )
            upload.aborted = True
        except Exception:
            pass
