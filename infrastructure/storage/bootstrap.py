"""
Storage bootstrap.

Provides dependency injection and lifecycle
management for the storage infrastructure,
creating and wiring all components together
for application startup.
"""

from __future__ import annotations

from typing import Any, Optional

from .batch import BatchTransfer
from .cache import StorageCache
from .client import StorageClient
from .compression import ZstdCompression
from .config import StorageConfig
from .encryption import StorageEncryption
from .health import StorageHealth
from .metrics import StorageMetrics
from .retry import StorageRetryConfig
from .service import StorageService
from .tracing import StorageTracing


class StorageBootstrap:
    """
    Storage bootstrap for production setup.

    Creates and wires all storage infrastructure
    components with dependency injection, providing
    a single entry point for application startup.

    Responsibilities:
    - Create StorageClient from config
    - Wire middleware pipeline components
    - Initialize health checker
    - Manage startup/shutdown lifecycle
    - Provide DI-friendly access to components

    Usage:
        bootstrap = StorageBootstrap(
            config=storage_config,
            redis_client=redis,
            encryption_key=key,
        )
        await bootstrap.startup()

        # Access service (main entry point)
        service = bootstrap.service
        meta = await service.upload("data/file.bin", data)

        # Shutdown
        await bootstrap.shutdown()
    """

    def __init__(
        self,
        config: StorageConfig,
        redis: Optional[Any] = None,
        encryption_key: Optional[bytes] = None,
        cache_ttl: int = 3600,
        retry_config: Optional[StorageRetryConfig] = None,
        tracer: Optional[Any] = None,
    ) -> None:
        """
        Initialize storage bootstrap.

        Args:
            config: Storage configuration.
            redis: Redis async client for caching.
            encryption_key: Fernet encryption key.
            cache_ttl: Cache TTL in seconds.
            retry_config: Retry policy configuration.
            tracer: OpenTelemetry tracer.
        """

        self._config = config
        self._redis = redis
        self._encryption_key = encryption_key
        self._cache_ttl = cache_ttl
        self._retry_config = retry_config
        self._tracer = tracer

        # Create components
        self._client = StorageClient(config=config)
        self._cache = (
            StorageCache(redis, ttl=cache_ttl)
            if redis
            else None
        )
        self._compression = ZstdCompression()
        self._encryption = (
            StorageEncryption(encryption_key)
            if encryption_key
            else None
        )
        self._metrics = StorageMetrics()
        self._tracing = StorageTracing()
        self._batch = BatchTransfer()

        if tracer:
            self._tracing.set_tracer(tracer)

        # Create service with pipeline
        self._service = StorageService(
            client=self._client,
            cache=self._cache,
            compression=self._compression,
            encryption=self._encryption,
            metrics=self._metrics,
            retry_config=retry_config,
            batch=self._batch,
        )

        # Create health checker
        self._health = StorageHealth(self._client)

    @property
    def client(self) -> StorageClient:
        """Get storage client."""
        return self._client

    @property
    def service(self) -> StorageService:
        """Get storage service (main entry point)."""
        return self._service

    @property
    def cache(self) -> Optional[StorageCache]:
        """Get storage cache."""
        return self._cache

    @property
    def compression(self) -> ZstdCompression:
        """Get compression provider."""
        return self._compression

    @property
    def encryption(self) -> Optional[StorageEncryption]:
        """Get encryption provider."""
        return self._encryption

    @property
    def metrics(self) -> StorageMetrics:
        """Get storage metrics."""
        return self._metrics

    @property
    def health(self) -> StorageHealth:
        """Get storage health checker."""
        return self._health

    @property
    def tracing(self) -> StorageTracing:
        """Get storage tracing hooks."""
        return self._tracing

    @property
    def config(self) -> StorageConfig:
        """Get storage configuration."""
        return self._config

    async def startup(self) -> None:
        """
        Start storage infrastructure.

        Initializes the storage client connection
        and prepares all components for use.
        """

        await self._client.startup()

    async def shutdown(self) -> None:
        """
        Shutdown storage infrastructure.

        Gracefully closes connections and
        releases resources.
        """

        await self._client.shutdown()

    async def check_health(self) -> dict:
        """
        Perform comprehensive health check.

        Returns:
            Health status dictionary.
        """

        result = await self._health.check()

        # Add pipeline component status
        result["cache"] = (
            self._cache.is_enabled
            if self._cache
            else False
        )
        result["compression"] = (
            self._compression.is_available
        )
        result["encryption"] = (
            self._encryption.is_initialized
            if self._encryption
            else False
        )
        result["tracing"] = self._tracing.is_enabled

        return result

    def get_di_registrations(self) -> dict:
        """
        Get component registrations for DI container.

        Returns:
            Dictionary mapping component types to instances.
        """

        registrations = {
            "StorageClient": self._client,
            "StorageService": self._service,
            "StorageCache": self._cache,
            "ZstdCompression": self._compression,
            "StorageEncryption": self._encryption,
            "StorageMetrics": self._metrics,
            "StorageHealth": self._health,
            "StorageTracing": self._tracing,
            "StorageBootstrap": self,
        }

        return {
            k: v
            for k, v in registrations.items()
            if v is not None
        }
