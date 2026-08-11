"""
Object Storage — low-level object storage abstraction supporting
multiple backends (S3, MinIO, Local, GCS, Azure).

Commit 16 Part 1.3
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ObjectStorageBackend(str, Enum):
    LOCAL = "local"
    S3 = "s3"
    MINIO = "minio"
    GCS = "gcs"
    AZURE = "azure"
    MEMORY = "memory"


@dataclass
class ObjectMetadata:
    key: str
    size_bytes: int = 0
    content_type: str = "application/octet-stream"
    etag: str = ""
    checksum_sha256: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    custom: dict[str, str] = field(default_factory=dict)


@dataclass
class StorageObject:
    metadata: ObjectMetadata
    data: bytes = b""
    path: str = ""


class ObjectStorage:
    """Abstract base for object storage backends."""

    async def put(self, key: str, data: bytes, *, metadata: Optional[dict[str, str]] = None) -> ObjectMetadata:
        raise NotImplementedError

    async def get(self, key: str) -> Optional[StorageObject]:
        raise NotImplementedError

    async def delete(self, key: str) -> bool:
        raise NotImplementedError

    async def list(self, prefix: str, *, max_keys: int = 1000) -> list[ObjectMetadata]:
        raise NotImplementedError

    async def exists(self, key: str) -> bool:
        raise NotImplementedError

    async def copy(self, source: str, destination: str) -> None:
        raise NotImplementedError

    async def head(self, key: str) -> Optional[ObjectMetadata]:
        raise NotImplementedError


class LocalObjectStorage(ObjectStorage):
    """Local filesystem-backed object storage."""

    def __init__(self, base_path: str = "data/lake") -> None:
        self.base_path = base_path
        os.makedirs(base_path, exist_ok=True)

    def _resolve(self, key: str) -> str:
        resolved = os.path.normpath(os.path.join(self.base_path, key))
        if not resolved.startswith(os.path.abspath(self.base_path)):
            raise ValueError(f"Path traversal detected: {key}")
        return resolved

    async def put(self, key: str, data: bytes, *, metadata: Optional[dict[str, str]] = None) -> ObjectMetadata:
        path = self._resolve(key)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(data)
        sha256 = hashlib.sha256(data).hexdigest()
        obj_meta = ObjectMetadata(
            key=key,
            size_bytes=len(data),
            etag=sha256[:16],
            checksum_sha256=sha256,
            custom=metadata or {},
        )
        logger.debug("PUT %s (%d bytes)", key, len(data))
        return obj_meta

    async def get(self, key: str) -> Optional[StorageObject]:
        path = self._resolve(key)
        if not os.path.isfile(path):
            return None
        with open(path, "rb") as f:
            data = f.read()
        return StorageObject(
            metadata=ObjectMetadata(key=key, size_bytes=len(data)),
            data=data,
            path=path,
        )

    async def delete(self, key: str) -> bool:
        path = self._resolve(key)
        if os.path.isfile(path):
            os.remove(path)
            logger.debug("DELETE %s", key)
            return True
        return False

    async def list(self, prefix: str, *, max_keys: int = 1000) -> list[ObjectMetadata]:
        base = self._resolve(prefix)
        results: list[ObjectMetadata] = []
        for root, _, files in os.walk(os.path.dirname(base) if os.path.isfile(base) else base):
            for name in files:
                full = os.path.join(root, name)
                rel = os.path.relpath(full, self.base_path).replace("\\", "/")
                if rel.startswith(prefix) and len(results) < max_keys:
                    results.append(
                        ObjectMetadata(key=rel, size_bytes=os.path.getsize(full))
                    )
        return results

    async def exists(self, key: str) -> bool:
        return os.path.isfile(self._resolve(key))

    async def copy(self, source: str, destination: str) -> None:
        import shutil
        shutil.copy2(self._resolve(source), self._resolve(destination))

    async def head(self, key: str) -> Optional[ObjectMetadata]:
        path = self._resolve(key)
        if not os.path.isfile(path):
            return None
        stat = os.stat(path)
        return ObjectMetadata(key=key, size_bytes=stat.st_size)


class S3ObjectStorage(ObjectStorage):
    """S3-compatible object storage (AWS S3, MinIO)."""

    def __init__(
        self,
        bucket: str,
        *,
        endpoint: Optional[str] = None,
        access_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        region: str = "us-east-1",
    ) -> None:
        self.bucket = bucket
        self.endpoint = endpoint
        self.access_key = access_key
        self.secret_key = secret_key
        self.region = region
        self._client = None
        logger.info("S3 storage configured: bucket=%s endpoint=%s", bucket, endpoint)

    async def _ensure_client(self):
        if self._client is None:
            try:
                import aioboto3
                session = aioboto3.Session()
                self._client = await session.client(
                    "s3",
                    endpoint_url=self.endpoint,
                    aws_access_key_id=self.access_key,
                    aws_secret_access_key=self.secret_key,
                    region_name=self.region,
                ).__aenter__()
            except ImportError:
                logger.warning("aioboto3 not installed; S3 operations will be no-ops")

    async def put(self, key: str, data: bytes, *, metadata: Optional[dict[str, str]] = None) -> ObjectMetadata:
        await self._ensure_client()
        if self._client:
            await self._client.put_object(
                Bucket=self.bucket, Key=key, Body=data, Metadata=metadata or {}
            )
        sha256 = hashlib.sha256(data).hexdigest()
        return ObjectMetadata(key=key, size_bytes=len(data), checksum_sha256=sha256)

    async def get(self, key: str) -> Optional[StorageObject]:
        await self._ensure_client()
        if self._client:
            try:
                resp = await self._client.get_object(Bucket=self.bucket, Key=key)
                data = await resp["Body"].read()
                return StorageObject(
                    metadata=ObjectMetadata(key=key, size_bytes=len(data)),
                    data=data,
                    path=f"s3://{self.bucket}/{key}",
                )
            except Exception:
                return None
        return None

    async def delete(self, key: str) -> bool:
        await self._ensure_client()
        if self._client:
            await self._client.delete_object(Bucket=self.bucket, Key=key)
            return True
        return False

    async def list(self, prefix: str, *, max_keys: int = 1000) -> list[ObjectMetadata]:
        await self._ensure_client()
        results: list[ObjectMetadata] = []
        if self._client:
            resp = await self._client.list_objects_v2(
                Bucket=self.bucket, Prefix=prefix, MaxKeys=max_keys
            )
            for obj in resp.get("Contents", []):
                results.append(
                    ObjectMetadata(key=obj["Key"], size_bytes=obj["Size"])
                )
        return results

    async def exists(self, key: str) -> bool:
        return await self.head(key) is not None

    async def copy(self, source: str, destination: str) -> None:
        await self._ensure_client()
        if self._client:
            await self._client.copy_object(
                Bucket=self.bucket,
                CopySource={"Bucket": self.bucket, "Key": source},
                Key=destination,
            )

    async def head(self, key: str) -> Optional[ObjectMetadata]:
        await self._ensure_client()
        if self._client:
            try:
                resp = await self._client.head_object(Bucket=self.bucket, Key=key)
                return ObjectMetadata(
                    key=key,
                    size_bytes=resp.get("ContentLength", 0),
                    etag=resp.get("ETag", ""),
                )
            except Exception:
                return None
        return None
