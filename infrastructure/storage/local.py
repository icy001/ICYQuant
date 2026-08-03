"""
Local filesystem storage provider.

Storage provider implementation using local
filesystem for development, testing, and
offline research scenarios.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Union

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


class LocalStorageProvider:
    """
    Local filesystem storage provider.

    Implements the StorageProvider interface
    using the local filesystem. Designed for
    development, unit testing, integration
    testing, and offline research scenarios.

    Features:
    - File-based object storage
    - Automatic directory creation
    - Preserves metadata alongside files
    - Supports all standard operations

    Note:
    This provider is NOT production-grade for
    high-concurrency scenarios. Use MinIO/S3
    for production deployments.
    """

    def __init__(
        self,
        config: StorageConfig,
        root: Optional[Union[Path, str]] = None,
    ) -> None:

        self._config = config

        if root is not None:
            self._root = (
                Path(root)
                if isinstance(root, str)
                else root
            )
        else:
            self._root = Path(
                config.endpoint
                if config.endpoint.startswith("/")
                or ":" in config.endpoint
                else f"./{config.endpoint}"
            )

        self._initialized = False

    @property
    def is_initialized(
        self,
    ) -> bool:
        """Check if provider is initialized."""
        return self._initialized

    @property
    def root(
        self,
    ) -> Path:
        """
        Get the root directory.

        Returns:
            Root directory path.
        """

        return self._root

    async def startup(
        self,
    ) -> None:
        """
        Initialize local storage provider.

        Creates the root directory if it doesn't exist.
        """

        try:
            self._root.mkdir(
                parents=True,
                exist_ok=True,
            )
            self._initialized = True
        except Exception as exc:
            self._initialized = False
            raise RuntimeError(
                f"Failed to initialize local storage: {exc}"
            ) from exc

    async def shutdown(
        self,
    ) -> None:
        """
        Shutdown local storage provider.

        No-op for local filesystem.
        """

        self._initialized = False

    def _get_path(
        self,
        key: str,
    ) -> Path:
        """
        Get full filesystem path for a key.

        Args:
            key: Object key (path).

        Returns:
            Full filesystem path.
        """

        return self._root / key

    async def upload(
        self,
        key: str,
        data: bytes,
        content_type: str = "application/octet-stream",
        metadata: Optional[Dict[str, str]] = None,
    ) -> ObjectMetadata:
        """
        Upload an object to local filesystem.

        Args:
            key: Object key (path).
            data: File content as bytes.
            content_type: MIME type (stored in metadata).
            metadata: Optional custom metadata.

        Returns:
            ObjectMetadata for the uploaded object.

        Raises:
            UploadError: If write fails.
        """

        try:
            path = self._get_path(key)
            path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )
            path.write_bytes(data)

            stat = path.stat()

            return ObjectMetadata(
                bucket=self._config.bucket,
                key=key,
                size=stat.st_size,
                etag=self._compute_etag(
                    path
                ),
                content_type=content_type,
                created_at=datetime.fromtimestamp(
                    stat.st_ctime,
                    tz=timezone.utc,
                ),
                updated_at=datetime.fromtimestamp(
                    stat.st_mtime,
                    tz=timezone.utc,
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
        Download an object from local filesystem.

        Args:
            key: Object key (path).

        Returns:
            Object content as bytes.

        Raises:
            ObjectNotFoundError: If file doesn't exist.
            DownloadError: If read fails.
        """

        path = self._get_path(key)

        if not path.exists():
            raise ObjectNotFoundError(
                key=key,
                bucket=self._config.bucket,
            )

        try:
            return path.read_bytes()
        except Exception as exc:
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
        Delete an object from local filesystem.

        Args:
            key: Object key (path).

        Raises:
            DeleteError: If deletion fails.
        """

        path = self._get_path(key)

        try:
            if path.exists():
                path.unlink()
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
        Check if an object exists locally.

        Args:
            key: Object key (path).

        Returns:
            True if the file exists.
        """

        return self._get_path(key).exists()

    async def list(
        self,
        prefix: str = "",
    ) -> List[ObjectMetadata]:
        """
        List objects locally with optional prefix.

        Args:
            prefix: Key prefix filter.

        Returns:
            List of ObjectMetadata objects.
        """

        result: List[ObjectMetadata] = []
        search_dir = (
            self._get_path(prefix)
            if prefix
            else self._root
        )

        if not search_dir.exists():
            return result

        try:
            for file_path in search_dir.rglob("*"):
                if file_path.is_file():
                    relative_key = str(
                        file_path.relative_to(
                            self._root
                        )
                    ).replace("\\", "/")

                    # Apply prefix filter
                    if prefix and not relative_key.startswith(
                        prefix.rstrip("/") + "/"
                    ):
                        continue

                    stat = file_path.stat()
                    result.append(
                        ObjectMetadata(
                            bucket=(
                                self._config.bucket
                            ),
                            key=relative_key,
                            size=stat.st_size,
                            etag=(
                                self._compute_etag(
                                    file_path
                                )
                            ),
                            content_type="",
                            created_at=(
                                datetime.fromtimestamp(
                                    stat.st_ctime,
                                    tz=timezone.utc,
                                )
                            ),
                            updated_at=(
                                datetime.fromtimestamp(
                                    stat.st_mtime,
                                    tz=timezone.utc,
                                )
                            ),
                        )
                    )
        except Exception:
            pass

        return result

    def _compute_etag(
        self,
        path: Path,
    ) -> str:
        """
        Compute a simple ETag for a file.

        Args:
            path: File path.

        Returns:
            ETag string (MD5-based).
        """

        import hashlib

        try:
            content = path.read_bytes()
            return hashlib.md5(content).hexdigest()
        except Exception:
            return ""

    # === Advanced Operations ===

    async def copy(
        self,
        source: str,
        target: str,
    ) -> ObjectMetadata:
        """
        Copy an object locally.

        Args:
            source: Source object key.
            target: Target object key.

        Returns:
            ObjectMetadata for the copied object.
        """

        import shutil

        src_path = self._get_path(source)
        tgt_path = self._get_path(target)

        if not src_path.exists():
            raise ObjectNotFoundError(
                key=source,
                bucket=self._config.bucket,
            )

        try:
            tgt_path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )
            shutil.copy2(src_path, tgt_path)

            stat = tgt_path.stat()
            return ObjectMetadata(
                bucket=self._config.bucket,
                key=target,
                size=stat.st_size,
                etag=self._compute_etag(tgt_path),
                content_type="",
                created_at=datetime.fromtimestamp(
                    stat.st_ctime,
                    tz=timezone.utc,
                ),
                updated_at=datetime.fromtimestamp(
                    stat.st_mtime,
                    tz=timezone.utc,
                ),
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
        Move an object locally.

        Args:
            source: Source object key.
            target: Target object key.

        Returns:
            ObjectMetadata for the moved object.
        """

        import shutil

        src_path = self._get_path(source)
        tgt_path = self._get_path(target)

        if not src_path.exists():
            raise ObjectNotFoundError(
                key=source,
                bucket=self._config.bucket,
            )

        try:
            tgt_path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )
            shutil.move(str(src_path), str(tgt_path))

            stat = tgt_path.stat()
            return ObjectMetadata(
                bucket=self._config.bucket,
                key=target,
                size=stat.st_size,
                etag=self._compute_etag(tgt_path),
                content_type="",
                created_at=datetime.fromtimestamp(
                    stat.st_ctime,
                    tz=timezone.utc,
                ),
                updated_at=datetime.fromtimestamp(
                    stat.st_mtime,
                    tz=timezone.utc,
                ),
            )
        except Exception as exc:
            raise UploadError(
                f"Failed to move {source} to {target}: {exc}",
                bucket=self._config.bucket,
                key=target,
            ) from exc

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

        path = self._get_path(key)

        if not path.exists():
            raise ObjectNotFoundError(
                key=key,
                bucket=self._config.bucket,
            )

        stat = path.stat()
        return ExtendedMetadata(
            bucket=self._config.bucket,
            key=key,
            size=stat.st_size,
            etag=self._compute_etag(path),
            content_type="",
            created_at=datetime.fromtimestamp(
                stat.st_ctime,
                tz=timezone.utc,
            ),
            updated_at=datetime.fromtimestamp(
                stat.st_mtime,
                tz=timezone.utc,
            ),
        )

    async def presign_download(
        self,
        key: str,
        expires: int = 3600,
    ) -> PresignedUrl:
        """
        Generate a presigned download URL.

        For local storage, returns a file:// URL.

        Args:
            key: Object key (path).
            expires: URL expiration in seconds (ignored).

        Returns:
            PresignedUrl for downloading.
        """

        path = self._get_path(key)
        return PresignedUrl(
            url=f"file://{path.absolute()}",
            expires_in=__import__("datetime").timedelta(
                seconds=expires
            ),
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

        For local storage, returns a file:// URL.

        Args:
            key: Object key (path).
            expires: URL expiration in seconds (ignored).

        Returns:
            PresignedUrl for uploading.
        """

        path = self._get_path(key)
        return PresignedUrl(
            url=f"file://{path.absolute()}",
            expires_in=__import__("datetime").timedelta(
                seconds=expires
            ),
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

        For local storage, uses a temp directory.

        Args:
            key: Target object key.

        Returns:
            MultipartUpload session.
        """

        import uuid

        return MultipartUpload(
            upload_id=str(uuid.uuid4()),
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

        Stores parts in temp directory.

        Args:
            upload: Multipart upload session.
            part_number: Part sequence number.
            data: Part data.

        Returns:
            Part ETag.
        """

        import hashlib

        temp_dir = self._root / ".multipart" / upload.upload_id
        temp_dir.mkdir(parents=True, exist_ok=True)

        part_path = temp_dir / f"part_{part_number}"
        part_path.write_bytes(data)

        etag = hashlib.md5(data).hexdigest()
        upload.add_part(part_number, len(data), etag)

        return etag

    async def complete_multipart_upload(
        self,
        upload: MultipartUpload,
    ) -> ObjectMetadata:
        """
        Complete a multipart upload.

        Concatenates all parts into final file.

        Args:
            upload: Multipart upload session.

        Returns:
            ObjectMetadata for the final object.
        """

        temp_dir = self._root / ".multipart" / upload.upload_id
        target_path = self._get_path(upload.object_key)

        target_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        with open(target_path, "wb") as f:
            for part in sorted(
                upload.parts,
                key=lambda p: p.part_number,
            ):
                part_path = temp_dir / f"part_{part.part_number}"
                if part_path.exists():
                    f.write(part_path.read_bytes())

        # Cleanup temp dir
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)

        upload.completed = True

        stat = target_path.stat()
        return ObjectMetadata(
            bucket=self._config.bucket,
            key=upload.object_key,
            size=stat.st_size,
            etag=self._compute_etag(target_path),
            content_type="",
            created_at=datetime.fromtimestamp(
                stat.st_ctime,
                tz=timezone.utc,
            ),
        )

    async def abort_multipart_upload(
        self,
        upload: MultipartUpload,
    ) -> None:
        """
        Abort a multipart upload.

        Cleans up temp directory.

        Args:
            upload: Multipart upload session.
        """

        import shutil

        temp_dir = self._root / ".multipart" / upload.upload_id
        shutil.rmtree(temp_dir, ignore_errors=True)

        upload.aborted = True
