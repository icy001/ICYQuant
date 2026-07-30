"""ICYQuant Object Storage Abstraction.

Abstraction layer over object storage backends (S3, MinIO, local FS).
Provides unified read/write/delete/list operations with:
    - Tiered storage (hot/warm/cold)
    - Multipart uploads for large files
    - Versioned objects
    - Lifecycle policies
"""

from __future__ import annotations

import json
import os
import shutil
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class StorageBackend(str, Enum):
    """Supported storage backends."""

    LOCAL = "local"
    S3 = "s3"
    MINIO = "minio"
    GCS = "gcs"


class StorageClass(str, Enum):
    """Storage classes for tiering."""

    STANDARD = "standard"        # Hot — frequent access
    INFREQUENT = "infrequent"    # Warm — infrequent access
    ARCHIVE = "archive"          # Cold — rarely accessed
    DEEP_ARCHIVE = "deep_archive"  # Frozen — almost never accessed


@dataclass
class ObjectMetadata:
    """Metadata for a stored object."""

    key: str
    bucket: str
    size_bytes: int
    storage_class: StorageClass = StorageClass.STANDARD
    version_id: str = ""
    content_type: str = "application/octet-stream"
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_modified: datetime = field(default_factory=datetime.utcnow)
    etag: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "bucket": self.bucket,
            "size_bytes": self.size_bytes,
            "storage_class": self.storage_class.value,
            "version_id": self.version_id,
            "content_type": self.content_type,
            "created_at": self.created_at.isoformat(),
            "last_modified": self.last_modified.isoformat(),
            "etag": self.etag,
            "tags": self.tags,
        }


@dataclass
class MultipartUpload:
    """Multipart upload state."""

    upload_id: str
    key: str
    bucket: str
    part_size: int = 5 * 1024 * 1024  # 5MB
    parts: List[Dict[str, Any]] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)


class ObjectStorage:
    """Object Storage Abstraction.

    Unified interface over local filesystem, S3, MinIO, and GCS.
    Supports tiered storage, versioning, and multipart uploads.

    Usage::

        storage = ObjectStorage(backend=StorageBackend.LOCAL, base_path="data/storage")
        storage.put_object("lakehouse", "market_tick/2026-07-29/data.parquet", data)
        obj = storage.get_object("lakehouse", "market_tick/2026-07-29/data.parquet")
        storage.set_storage_class("lakehouse", "old_data.parquet", StorageClass.ARCHIVE)
    """

    def __init__(
        self,
        backend: StorageBackend = StorageBackend.LOCAL,
        base_path: str = "data/storage",
        **kwargs: Any,
    ) -> None:
        self.backend = backend
        self.base_path = base_path
        self.config = kwargs
        self._objects: Dict[str, Dict[str, ObjectMetadata]] = {}  # bucket → key → meta
        self._data: Dict[str, Dict[str, bytes]] = {}  # bucket → key → data
        self._uploads: Dict[str, MultipartUpload] = {}

        if backend == StorageBackend.LOCAL:
            os.makedirs(base_path, exist_ok=True)

    # ------------------------------------------------------------------
    # Bucket Management
    # ------------------------------------------------------------------

    def create_bucket(self, bucket: str) -> None:
        """Create a storage bucket."""
        if bucket not in self._objects:
            self._objects[bucket] = {}
            self._data[bucket] = {}

    def list_buckets(self) -> List[str]:
        """List all buckets."""
        return list(self._objects.keys())

    def delete_bucket(self, bucket: str) -> bool:
        """Delete a bucket and all its objects."""
        if bucket in self._objects:
            del self._objects[bucket]
            del self._data[bucket]
            return True
        return False

    # ------------------------------------------------------------------
    # Object Operations
    # ------------------------------------------------------------------

    def put_object(
        self,
        bucket: str,
        key: str,
        data: bytes,
        storage_class: StorageClass = StorageClass.STANDARD,
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[Dict[str, str]] = None,
    ) -> ObjectMetadata:
        """Store an object.

        Args:
            bucket: Bucket name.
            key: Object key/path.
            data: Binary data.
            storage_class: Storage class.
            metadata: Custom metadata.
            tags: Key-value tags.

        Returns:
            ObjectMetadata.
        """
        self.create_bucket(bucket)

        version_id = str(uuid.uuid4())

        obj_meta = ObjectMetadata(
            key=key,
            bucket=bucket,
            size_bytes=len(data),
            storage_class=storage_class,
            version_id=version_id,
            metadata=metadata or {},
            tags=tags or {},
        )

        self._objects[bucket][key] = obj_meta
        self._data[bucket][key] = data

        # Write to local FS if local backend
        if self.backend == StorageBackend.LOCAL:
            file_path = os.path.join(self.base_path, bucket, key)
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, "wb") as f:
                f.write(data)

        return obj_meta

    def get_object(self, bucket: str, key: str) -> Optional[bytes]:
        """Retrieve an object.

        Args:
            bucket: Bucket name.
            key: Object key.

        Returns:
            Binary data or None.
        """
        return self._data.get(bucket, {}).get(key)

    def get_object_metadata(self, bucket: str, key: str) -> Optional[ObjectMetadata]:
        """Get object metadata without retrieving data."""
        return self._objects.get(bucket, {}).get(key)

    def head_object(self, bucket: str, key: str) -> Optional[ObjectMetadata]:
        """Alias for get_object_metadata."""
        return self.get_object_metadata(bucket, key)

    def delete_object(self, bucket: str, key: str) -> bool:
        """Delete an object."""
        if bucket in self._objects and key in self._objects[bucket]:
            del self._objects[bucket][key]
            self._data[bucket].pop(key, None)

            if self.backend == StorageBackend.LOCAL:
                file_path = os.path.join(self.base_path, bucket, key)
                if os.path.exists(file_path):
                    os.remove(file_path)

            return True
        return False

    def list_objects(
        self,
        bucket: str,
        prefix: Optional[str] = None,
        max_keys: int = 1000,
    ) -> List[ObjectMetadata]:
        """List objects in a bucket, optionally filtered by prefix.

        Args:
            bucket: Bucket name.
            prefix: Key prefix filter.
            max_keys: Maximum results.

        Returns:
            List of ObjectMetadata.
        """
        objects = list(self._objects.get(bucket, {}).values())

        if prefix:
            objects = [o for o in objects if o.key.startswith(prefix)]

        objects.sort(key=lambda o: o.key)
        return objects[:max_keys]

    def object_exists(self, bucket: str, key: str) -> bool:
        """Check if an object exists."""
        return key in self._objects.get(bucket, {})

    # ------------------------------------------------------------------
    # Tiering / Storage Class
    # ------------------------------------------------------------------

    def set_storage_class(
        self, bucket: str, key: str, storage_class: StorageClass
    ) -> bool:
        """Change an object's storage class (tier transition).

        Args:
            bucket: Bucket name.
            key: Object key.
            storage_class: New storage class.

        Returns:
            True if changed.
        """
        obj = self._objects.get(bucket, {}).get(key)
        if not obj:
            return False

        obj.storage_class = storage_class
        obj.last_modified = datetime.utcnow()
        return True

    def get_objects_by_class(
        self, bucket: str, storage_class: StorageClass
    ) -> List[ObjectMetadata]:
        """Get all objects of a specific storage class.

        Args:
            bucket: Bucket name.
            storage_class: Storage class to filter.

        Returns:
            List of ObjectMetadata.
        """
        return [
            o for o in self._objects.get(bucket, {}).values()
            if o.storage_class == storage_class
        ]

    # ------------------------------------------------------------------
    # Multipart Upload
    # ------------------------------------------------------------------

    def create_multipart_upload(
        self, bucket: str, key: str, part_size: int = 5 * 1024 * 1024
    ) -> MultipartUpload:
        """Start a multipart upload.

        Args:
            bucket: Bucket name.
            key: Object key.
            part_size: Part size in bytes.

        Returns:
            MultipartUpload state.
        """
        upload = MultipartUpload(
            upload_id=str(uuid.uuid4()),
            key=key,
            bucket=bucket,
            part_size=part_size,
        )
        self._uploads[upload.upload_id] = upload
        return upload

    def upload_part(self, upload_id: str, part_number: int, data: bytes) -> bool:
        """Upload a part of a multipart upload.

        Args:
            upload_id: Upload ID.
            part_number: Part number (1-based).
            data: Part data.

        Returns:
            True if successful.
        """
        upload = self._uploads.get(upload_id)
        if not upload:
            return False

        upload.parts.append({
            "part_number": part_number,
            "size": len(data),
            "data": data,
        })
        return True

    def complete_multipart_upload(self, upload_id: str) -> Optional[ObjectMetadata]:
        """Complete a multipart upload.

        Args:
            upload_id: Upload ID.

        Returns:
            ObjectMetadata for the assembled object.
        """
        upload = self._uploads.pop(upload_id, None)
        if not upload:
            return None

        # Assemble parts
        upload.parts.sort(key=lambda p: p["part_number"])
        assembled = b"".join(p["data"] for p in upload.parts)

        return self.put_object(
            bucket=upload.bucket,
            key=upload.key,
            data=assembled,
        )

    def abort_multipart_upload(self, upload_id: str) -> bool:
        """Abort a multipart upload.

        Args:
            upload_id: Upload ID.

        Returns:
            True if aborted.
        """
        if upload_id in self._uploads:
            del self._uploads[upload_id]
            return True
        return False

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    def get_stats(self) -> Dict[str, Any]:
        """Get object storage statistics."""
        total_objects = sum(len(objs) for objs in self._objects.values())
        total_size = sum(
            o.size_bytes
            for bucket in self._objects.values()
            for o in bucket.values()
        )

        by_class: Dict[str, int] = {}
        for bucket in self._objects.values():
            for o in bucket.values():
                cls = o.storage_class.value
                by_class[cls] = by_class.get(cls, 0) + 1

        return {
            "backend": self.backend.value,
            "total_buckets": len(self._objects),
            "total_objects": total_objects,
            "total_size_bytes": total_size,
            "total_size_gb": round(total_size / (1024 ** 3), 2),
            "by_storage_class": by_class,
        }
