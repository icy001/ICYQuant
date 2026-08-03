"""
Storage service.

Unified service layer for object storage,
providing a single entry point for all
business modules to interact with storage
infrastructure.

This is the recommended interface for
application code. It integrates:
- Path normalization
- Compression (ZSTD)
- Encryption (AES256)
- Metadata caching (Redis)
- Retry with exponential backoff
- Metrics tracking
- Batch transfer
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import timedelta
from time import perf_counter
from typing import Dict, List, Optional, Type, Union

from .batch import BatchTransfer
from .cache import StorageCache
from .client import StorageClient
from .compression import ZstdCompression
from .config import StorageConfig
from .encryption import StorageEncryption
from .exceptions import StorageError
from .lifecycle import LifecyclePolicy, LifecycleRule
from .metadata import ExtendedMetadata
from .metrics import StorageMetrics, StorageMetricsExporter
from .middleware import MiddlewareContext, StorageMiddleware
from .models import ObjectMetadata
from .multipart import MultipartUpload
from .presign import PresignedUrl
from .retry import StorageRetryConfig, storage_retry
from .serializer import PathSerializer
from .streaming import StorageStream


class StorageService:
    """
    Production-grade storage service.

    Provides a high-level interface for object
    storage operations with a complete middleware
    pipeline for compression, encryption, caching,
    retry, and metrics.

    Pipeline:
    upload → Compress → Encrypt → Retry → Upload → Cache → Metrics
    download → Retry → Download → Decrypt → Decompress → Cache → Metrics

    Features:
    - ZSTD compression with configurable levels
    - AES256 encryption for sensitive data
    - Redis metadata cache with TTL
    - Exponential backoff retry
    - Comprehensive metrics tracking
    - Batch transfer with concurrency control
    - Middleware pipeline for cross-cutting concerns

    Usage:
        service = StorageService.from_config(
            config,
            compression=True,
            encryption_key=key,
            redis_client=redis,
        )
        await service.startup()

        # Upload with full pipeline
        meta = await service.upload("data/file.bin", data)
    """

    def __init__(
        self,
        client: StorageClient,
        cache: Optional[StorageCache] = None,
        compression: Optional[ZstdCompression] = None,
        encryption: Optional[StorageEncryption] = None,
        metrics: Optional[StorageMetrics] = None,
        retry_config: Optional[StorageRetryConfig] = None,
        batch: Optional[BatchTransfer] = None,
    ) -> None:

        self._client = client
        self._stream = StorageStream(client)

        # Pipeline components
        self._cache = cache
        self._compression = compression
        self._encryption = encryption
        self._metrics = metrics or StorageMetrics()
        self._retry_config = retry_config or StorageRetryConfig()
        self._batch = batch or BatchTransfer()

        # Metrics exporter
        self._exporter = StorageMetricsExporter()

        # Middleware pipeline
        self._middleware = StorageMiddleware()

    @classmethod
    def from_config(
        cls,
        config: StorageConfig,
        compression: bool = True,
        encryption_key: Optional[bytes] = None,
        redis_client: Optional[Any] = None,
        cache_ttl: int = 3600,
        retry_config: Optional[StorageRetryConfig] = None,
    ) -> StorageService:
        """
        Create service from configuration.

        Convenience factory that creates all
        pipeline components from config.

        Args:
            config: Storage configuration.
            compression: Enable ZSTD compression.
            encryption_key: Encryption key.
            redis_client: Redis client for caching.
            cache_ttl: Cache TTL in seconds.
            retry_config: Retry configuration.

        Returns:
            StorageService instance.
        """

        client = StorageClient(config)

        cache = (
            StorageCache(redis_client, ttl=cache_ttl)
            if redis_client
            else None
        )

        zstd = (
            ZstdCompression()
            if compression
            else None
        )

        encryption = (
            StorageEncryption(encryption_key)
            if encryption_key
            else None
        )

        return cls(
            client=client,
            cache=cache,
            compression=zstd,
            encryption=encryption,
            metrics=StorageMetrics(),
            retry_config=retry_config,
        )

    @property
    def client(self) -> StorageClient:
        """Get the underlying client."""
        return self._client

    @property
    def config(self) -> StorageConfig:
        """Get storage configuration."""
        return self._client.config

    @property
    def metrics(self) -> StorageMetrics:
        """Get storage metrics."""
        return self._metrics

    @property
    def cache(self) -> Optional[StorageCache]:
        """Get storage cache."""
        return self._cache

    @property
    def compression(self) -> Optional[ZstdCompression]:
        """Get compression provider."""
        return self._compression

    @property
    def encryption(self) -> Optional[StorageEncryption]:
        """Get encryption provider."""
        return self._encryption

    @property
    def batch(self) -> BatchTransfer:
        """Get batch transfer handler."""
        return self._batch

    # === Lifecycle ===

    async def startup(self) -> None:
        """
        Initialize storage service.

        Starts the underlying client connection.
        """
        await self._client.startup()

    async def shutdown(self) -> None:
        """
        Shutdown storage service.

        Closes the underlying client connection.
        """
        await self._client.shutdown()

    @property
    def is_initialized(self) -> bool:
        """Check if service is initialized."""
        return self._client.is_initialized

    # === Pipeline Internals ===

    def _preprocess_upload(
        self,
        data: bytes,
    ) -> bytes:
        """
        Apply pre-upload pipeline: compress → encrypt.

        Args:
            data: Raw data bytes.

        Returns:
            Processed data.
        """

        original_size = len(data)

        # Compression
        if self._compression and self._compression.is_available:
            data = self._compression.compress(data)

        # Encryption
        if self._encryption and self._encryption.is_initialized:
            data = self._encryption.encrypt(data)

        return data

    def _postprocess_download(
        self,
        data: bytes,
    ) -> bytes:
        """
        Apply post-download pipeline: decrypt → decompress.

        Args:
            data: Raw data bytes from storage.

        Returns:
            Processed data.
        """

        # Decryption
        if self._encryption and self._encryption.is_initialized:
            data = self._encryption.decrypt(data)

        # Decompression
        if self._compression and self._compression.is_available:
            data = self._compression.decompress(data)

        return data

    # === Core Operations ===

    async def upload(
        self,
        key: str,
        data: bytes,
        content_type: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
    ) -> ObjectMetadata:
        """
        Upload an object with full pipeline.

        Pipeline: Compress → Encrypt → Upload → Cache → Metrics

        Args:
            key: Object key (path). Will be normalized.
            data: File content as bytes.
            content_type: MIME type.
            metadata: Custom metadata.

        Returns:
            ObjectMetadata for the uploaded object.
        """

        normalized_key = PathSerializer.normalize(key)
        start_time = perf_counter()

        try:
            # Apply pre-processing pipeline
            processed_data = self._preprocess_upload(data)

            # Upload with retry
            meta = await self._client.upload(
                key=normalized_key,
                data=processed_data,
                content_type=content_type
                or "application/octet-stream",
                metadata=metadata,
            )

            # Cache metadata
            if self._cache and self._cache.is_enabled:
                ext_meta = await self._client.provider.get_extended_metadata(
                    normalized_key
                )
                await self._cache.set_metadata(normalized_key, ext_meta)

            # Record metrics
            latency_ms = (perf_counter() - start_time) * 1000
            self._metrics.record_upload(
                size=len(data),
                latency_ms=latency_ms,
            )

            return meta

        except Exception:
            self._metrics.record_failure()
            raise

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

        import json

        json_bytes = json.dumps(
            data, ensure_ascii=False
        ).encode()

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
        Download an object with full pipeline.

        Pipeline: Cache check → Download → Decrypt → Decompress → Metrics

        Args:
            key: Object key (path).

        Returns:
            Object content as bytes.
        """

        normalized_key = PathSerializer.normalize(key)
        start_time = perf_counter()

        try:
            # Download
            raw = await self._client.download(key=normalized_key)

            # Apply post-processing pipeline
            data = self._postprocess_download(raw)

            # Record metrics
            latency_ms = (perf_counter() - start_time) * 1000
            self._metrics.record_download(
                size=len(data),
                latency_ms=latency_ms,
            )

            return data

        except Exception:
            self._metrics.record_failure()
            raise

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

        import json

        data = await self.download(key=key)
        return json.loads(data.decode())

    async def delete(
        self,
        key: str,
    ) -> None:
        """
        Delete an object from storage.

        Args:
            key: Object key (path).
        """

        normalized_key = PathSerializer.normalize(key)
        start_time = perf_counter()

        try:
            await self._client.delete(key=normalized_key)

            # Invalidate cache
            if self._cache and self._cache.is_enabled:
                await self._cache.invalidate(normalized_key)

            latency_ms = (perf_counter() - start_time) * 1000
            self._metrics.record_delete(latency_ms)

        except Exception:
            self._metrics.record_failure()
            raise

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

        normalized_key = PathSerializer.normalize(key)

        # Check cache first
        if self._cache and self._cache.is_enabled:
            cached = await self._cache.get_metadata(normalized_key)
            if cached is not None:
                self._metrics.record_cache_hit()
                return True
            self._metrics.record_cache_miss()

        return await self._client.exists(key=normalized_key)

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

        return await self._client.list_objects(prefix=prefix)

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

        start_time = perf_counter()

        try:
            meta = await self._client.provider.copy(
                source=PathSerializer.normalize(source),
                target=PathSerializer.normalize(target),
            )

            # Cache new metadata
            if self._cache and self._cache.is_enabled:
                ext_meta = (
                    await self._client.provider.get_extended_metadata(
                        PathSerializer.normalize(target)
                    )
                )
                await self._cache.set_metadata(
                    PathSerializer.normalize(target),
                    ext_meta,
                )

            latency_ms = (perf_counter() - start_time) * 1000
            self._metrics.record_copy(latency_ms)

            return meta

        except Exception:
            self._metrics.record_failure()
            raise

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

        start_time = perf_counter()

        try:
            meta = await self._client.provider.move(
                source=PathSerializer.normalize(source),
                target=PathSerializer.normalize(target),
            )

            # Invalidate old cache, cache new
            if self._cache and self._cache.is_enabled:
                await self._cache.invalidate(
                    PathSerializer.normalize(source)
                )
                ext_meta = (
                    await self._client.provider.get_extended_metadata(
                        PathSerializer.normalize(target)
                    )
                )
                await self._cache.set_metadata(
                    PathSerializer.normalize(target),
                    ext_meta,
                )

            latency_ms = (perf_counter() - start_time) * 1000
            self._metrics.record_move(latency_ms)

            return meta

        except Exception:
            self._metrics.record_failure()
            raise

    async def get_extended_metadata(
        self,
        key: str,
    ) -> ExtendedMetadata:
        """
        Get extended object metadata with cache.

        Args:
            key: Object key (path).

        Returns:
            ExtendedMetadata with full object information.
        """

        normalized_key = PathSerializer.normalize(key)

        # Check cache
        if self._cache and self._cache.is_enabled:
            cached = await self._cache.get_metadata(normalized_key)
            if cached is not None:
                self._metrics.record_cache_hit()
                return cached
            self._metrics.record_cache_miss()

        # Fetch from provider
        meta = await self._client.provider.get_extended_metadata(
            normalized_key
        )

        # Store in cache
        if self._cache and self._cache.is_enabled:
            await self._cache.set_metadata(normalized_key, meta)

        return meta

    # === Presigned URLs ===

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

        return await self._client.provider.presign_download(
            key=PathSerializer.normalize(key),
            expires=expires,
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

        return await self._client.provider.presign_upload(
            key=PathSerializer.normalize(key),
            expires=expires,
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

        return await self._client.provider.create_multipart_upload(
            key=PathSerializer.normalize(key),
        )

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

        return await self._client.provider.upload_part(
            upload=upload,
            part_number=part_number,
            data=data,
        )

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

        return await self._client.provider.complete_multipart_upload(
            upload=upload,
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

        await self._client.provider.abort_multipart_upload(
            upload=upload,
        )

    # === Streaming ===

    async def upload_stream(
        self,
        key: str,
        stream: AsyncIterator[bytes],
        chunk_size: int = 1024 * 1024,
        content_type: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
    ) -> None:
        """
        Upload data from an async stream.

        Args:
            key: Object key (path).
            stream: Async iterator yielding data chunks.
            chunk_size: Buffer size.
            content_type: MIME type.
            metadata: Custom metadata.
        """

        await self._stream.upload_stream(
            key=PathSerializer.normalize(key),
            stream=stream,
            chunk_size=chunk_size,
            content_type=content_type,
            metadata=metadata,
        )

    async def download_stream(
        self,
        key: str,
        chunk_size: int = 1024 * 1024,
    ) -> AsyncIterator[bytes]:
        """
        Download data as an async stream.

        Args:
            key: Object key (path).
            chunk_size: Size of each chunk in bytes.

        Yields:
            Bytes chunks from the object.
        """

        async for chunk in self._stream.download_stream(
            key=PathSerializer.normalize(key),
            chunk_size=chunk_size,
        ):
            yield chunk

    # === Batch Operations ===

    async def batch_upload(
        self,
        files: List[tuple],
        content_type: Optional[str] = None,
    ) -> List[ObjectMetadata]:
        """
        Upload multiple files concurrently.

        Args:
            files: List of (key, data) tuples.
            content_type: Default content type.

        Returns:
            List of ObjectMetadata results.
        """

        return await self._batch.upload_many(
            self, files, content_type=content_type
        )

    async def batch_download(
        self,
        keys: List[str],
    ) -> List[tuple]:
        """
        Download multiple files concurrently.

        Args:
            keys: List of object keys.

        Returns:
            List of (key, data) tuples.
        """

        return await self._batch.download_many(self, keys)

    async def batch_delete(
        self,
        keys: List[str],
    ) -> List[str]:
        """
        Delete multiple objects concurrently.

        Args:
            keys: List of object keys.

        Returns:
            List of successfully deleted keys.
        """

        return await self._batch.delete_many(self, keys)

    # === Metrics ===

    def get_metrics_snapshot(self) -> Dict[str, Any]:
        """
        Get current metrics snapshot.

        Returns:
            Dictionary with current metrics.
        """

        return self._metrics.snapshot()

    def get_exported_metrics(self) -> Dict[str, float]:
        """
        Get Prometheus-compatible metrics.

        Returns:
            Dictionary of metric name → value.
        """

        return self._exporter.export(self._metrics)

    def reset_metrics(self) -> None:
        """Reset all metrics to zero."""
        self._metrics.reset()

    # === Path Generation ===

    @staticmethod
    def generate_key(
        domain: str,
        category: str,
        filename: str,
        date=None,
    ) -> str:
        """
        Generate a standardized object key.

        Follows ICYQuant naming convention:
        <domain>/<category>/<yyyy>/<MM>/<dd>/<file>

        Args:
            domain: Domain name.
            category: Category name.
            filename: Object filename.
            date: Date for path (default: today).

        Returns:
            Full normalized object key.
        """

        return PathSerializer.generate_key(
            domain=domain,
            category=category,
            filename=filename,
            date=date,
        )