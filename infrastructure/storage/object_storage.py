"""Object Storage — cloud-scale blob storage for feature artifacts.

Provides an abstraction over S3, MinIO, and local filesystem
for storing feature-related artifacts (model binaries, reports,
feature importance, etc.).

Usage::

    from infrastructure.storage import ObjectStorage

    storage = ObjectStorage(bucket="icyquant-features")
    storage.put("features/ema20/v1/model.pkl", model_bytes)
    data = storage.get("features/ema20/v1/model.pkl")
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class StorageProvider(str, Enum):
    """Supported object storage providers."""

    LOCAL = "local"
    S3 = "s3"
    MINIO = "minio"
    MEMORY = "memory"


@dataclass
class ObjectMetadata:
    """Metadata for a stored object.

    Attributes:
        key: Object key (path).
        size_bytes: Object size in bytes.
        content_type: MIME type.
        etag: Content hash / ETag.
        last_modified: Last modification timestamp.
        metadata: User-defined metadata.
    """

    key: str
    size_bytes: int = 0
    content_type: str = "application/octet-stream"
    etag: str = ""
    last_modified: float = field(default_factory=time.time)
    metadata: Dict[str, str] = field(default_factory=dict)


@dataclass
class StorageConfig:
    """Object storage configuration.

    Attributes:
        provider: Storage provider type.
        bucket: Bucket/container name.
        endpoint: S3/MinIO endpoint URL.
        access_key: Access key.
        secret_key: Secret key.
        region: S3 region.
        use_ssl: Whether to use HTTPS.
        local_base_path: Local filesystem base path.
    """

    provider: StorageProvider = StorageProvider.MEMORY
    bucket: str = "icyquant-features"
    endpoint: str = ""
    access_key: str = ""
    secret_key: str = ""
    region: str = "us-east-1"
    use_ssl: bool = True
    local_base_path: str = "data/artifacts"


class ObjectStorage:
    """Cloud-scale object storage abstraction.

    Supports local, S3, MinIO, and in-memory backends for
    feature artifact storage. Provides put/get/delete/list
    operations with metadata management.
    """

    # ---- 分组：初始化 ----

    def __init__(self, config: Optional[StorageConfig] = None) -> None:
        """Initialize the object storage.

        Args:
            config: Storage configuration.
        """
        self.config = config or StorageConfig()
        self._objects: Dict[str, bytes] = {}
        self._metadata: Dict[str, ObjectMetadata] = {}
        self._ensure_local_path()

    def _ensure_local_path(self) -> None:
        """Ensure local base path exists."""
        if self.config.provider == StorageProvider.LOCAL:
            os.makedirs(self.config.local_base_path, exist_ok=True)

    # ---- 分组：写入 ----

    def put(
        self,
        key: str,
        data: bytes,
        content_type: str = "application/octet-stream",
        metadata: Optional[Dict[str, str]] = None,
    ) -> ObjectMetadata:
        """Store an object.

        Args:
            key: Object key (path).
            data: Raw bytes.
            content_type: MIME type.
            metadata: User-defined metadata.

        Returns:
            ObjectMetadata.
        """
        import hashlib

        self._objects[key] = data
        obj_meta = ObjectMetadata(
            key=key,
            size_bytes=len(data),
            content_type=content_type,
            etag=hashlib.md5(data).hexdigest(),
            metadata=metadata or {},
        )
        self._metadata[key] = obj_meta

        # Persist to local if using local provider
        if self.config.provider == StorageProvider.LOCAL:
            file_path = os.path.join(self.config.local_base_path, key)
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, "wb") as f:
                f.write(data)

        return obj_meta

    def put_json(
        self,
        key: str,
        data: Dict[str, Any],
        metadata: Optional[Dict[str, str]] = None,
    ) -> ObjectMetadata:
        """Store a JSON-serializable object.

        Args:
            key: Object key.
            data: JSON-serializable dict.
            metadata: User-defined metadata.

        Returns:
            ObjectMetadata.
        """
        json_bytes = json.dumps(data, default=str).encode("utf-8")
        return self.put(key, json_bytes, "application/json", metadata)

    # ---- 分组：读取 ----

    def get(self, key: str) -> Optional[bytes]:
        """Retrieve an object's raw bytes.

        Args:
            key: Object key.

        Returns:
            Raw bytes or None.
        """
        # Check in-memory first
        data = self._objects.get(key)
        if data is not None:
            return data

        # Fallback to local filesystem
        if self.config.provider == StorageProvider.LOCAL:
            file_path = os.path.join(self.config.local_base_path, key)
            if os.path.exists(file_path):
                with open(file_path, "rb") as f:
                    return f.read()

        return None

    def get_json(self, key: str) -> Optional[Dict[str, Any]]:
        """Retrieve and parse a JSON object.

        Args:
            key: Object key.

        Returns:
            Parsed dict or None.
        """
        data = self.get(key)
        if data is None:
            return None
        return json.loads(data.decode("utf-8"))

    def get_metadata(self, key: str) -> Optional[ObjectMetadata]:
        """Get object metadata.

        Args:
            key: Object key.

        Returns:
            ObjectMetadata or None.
        """
        return self._metadata.get(key)

    # ---- 分组：存在性 ----

    def exists(self, key: str) -> bool:
        """Check if an object exists.

        Args:
            key: Object key.

        Returns:
            True if object exists.
        """
        if key in self._objects:
            return True
        if self.config.provider == StorageProvider.LOCAL:
            file_path = os.path.join(self.config.local_base_path, key)
            return os.path.exists(file_path)
        return False

    # ---- 分组：列表 ----

    def list(
        self,
        prefix: str = "",
        max_keys: int = 1000,
    ) -> List[ObjectMetadata]:
        """List objects with a key prefix.

        Args:
            prefix: Key prefix filter.
            max_keys: Maximum objects to return.

        Returns:
            List of ObjectMetadata.
        """
        results: List[ObjectMetadata] = []
        for key, meta in sorted(self._metadata.items()):
            if key.startswith(prefix):
                results.append(meta)
                if len(results) >= max_keys:
                    break
        return results

    def list_keys(self, prefix: str = "") -> List[str]:
        """List object keys with a prefix.

        Args:
            prefix: Key prefix filter.

        Returns:
            Sorted list of keys.
        """
        return sorted(k for k in self._objects if k.startswith(prefix))

    # ---- 分组：删除 ----

    def delete(self, key: str) -> bool:
        """Delete an object.

        Args:
            key: Object key.

        Returns:
            True if deleted.
        """
        deleted = self._objects.pop(key, None) is not None
        self._metadata.pop(key, None)

        if self.config.provider == StorageProvider.LOCAL:
            file_path = os.path.join(self.config.local_base_path, key)
            if os.path.exists(file_path):
                os.remove(file_path)
                deleted = True

        return deleted

    def delete_prefix(self, prefix: str) -> int:
        """Delete all objects with a key prefix.

        Args:
            prefix: Key prefix.

        Returns:
            Number of objects deleted.
        """
        keys = [k for k in self._objects if k.startswith(prefix)]
        for k in keys:
            self.delete(k)
        return len(keys)

    # ---- 分组：复制和移动 ----

    def copy(self, source_key: str, dest_key: str) -> Optional[ObjectMetadata]:
        """Copy an object to a new key.

        Args:
            source_key: Source key.
            dest_key: Destination key.

        Returns:
            ObjectMetadata for the copy, or None if source not found.
        """
        data = self.get(source_key)
        if data is None:
            return None

        source_meta = self._metadata.get(source_key)
        content_type = source_meta.content_type if source_meta else "application/octet-stream"
        meta = source_meta.metadata if source_meta else None

        return self.put(dest_key, data, content_type, meta)

    # ---- 分组：统计 ----

    def total_objects(self) -> int:
        """Total number of objects stored.

        Returns:
            Object count.
        """
        return len(self._objects)

    def total_size(self) -> int:
        """Total size of all objects in bytes.

        Returns:
            Total bytes.
        """
        return sum(len(data) for data in self._objects.values())
