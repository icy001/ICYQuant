"""
Storage middleware pipeline.

Provides a middleware pattern for storage
operations, enabling cross-cutting concerns
like caching, compression, encryption,
metrics, and auditing to be added without
modifying core service logic.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, TypeVar
from time import perf_counter

from .cache import StorageCache
from .compression import ZstdCompression
from .encryption import StorageEncryption
from .metrics import StorageMetrics

T = TypeVar("T")


@dataclass
class MiddlewareContext:
    """
    Context passed through middleware pipeline.

    Contains operation metadata and shared
    state for middleware processing.

    Attributes:
        operation: Operation name (upload, download, etc.).
        key: Object key.
        data: Data payload (mutable).
        metadata: Operation metadata.
        extra: Extra context data.
    """

    operation: str = ""
    key: str = ""
    data: Any = None
    metadata: Dict[str, Any] = field(
        default_factory=dict
    )
    extra: Dict[str, Any] = field(
        default_factory=dict
    )


class StorageMiddleware:
    """
    Storage middleware pipeline.

    Manages a chain of middleware processors
    that intercept storage operations. Each
    middleware can modify the request context
    before/after the operation.

    Middleware execution order (upload):
    1. Compression middleware
    2. Encryption middleware
    3. Cache middleware (metadata check)
    4. Execute actual operation
    5. Cache middleware (metadata store)
    6. Metrics middleware

    Usage:
        pipeline = StorageMiddleware()
        pipeline.add(compression_middleware)
        pipeline.add(encryption_middleware)

        async with pipeline.process(ctx):
            # Execute actual operation
            result = await do_upload(ctx.data)
    """

    def __init__(
        self,
    ) -> None:
        """
        Initialize middleware pipeline.
        """

        self._pre_hooks: List[
            Callable[
                [MiddlewareContext],
                Any,
            ]
        ] = []
        self._post_hooks: List[
            Callable[
                [MiddlewareContext, Any],
                Any,
            ]
        ] = []

    def add_pre_hook(
        self,
        hook: Callable[
            [MiddlewareContext],
            Any,
        ],
    ) -> None:
        """
        Add a pre-operation hook.

        Args:
            hook: Async function to run before operation.
        """

        self._pre_hooks.append(hook)

    def add_post_hook(
        self,
        hook: Callable[
            [MiddlewareContext, Any],
            Any,
        ],
    ) -> None:
        """
        Add a post-operation hook.

        Args:
            hook: Async function to run after operation.
        """

        self._post_hooks.append(hook)

    async def process(
        self,
        ctx: MiddlewareContext,
    ) -> MiddlewareContext:
        """
        Process request through pre-hooks.

        Args:
            ctx: Middleware context.

        Returns:
            Processed context.
        """

        for hook in self._pre_hooks:
            result = await hook(ctx)
            if result is not None:
                ctx = result

        return ctx

    async def finalize(
        self,
        ctx: MiddlewareContext,
        result: Any,
    ) -> Any:
        """
        Process result through post-hooks.

        Args:
            ctx: Original middleware context.
            result: Operation result.

        Returns:
            Processed result.
        """

        for hook in self._post_hooks:
            result = await hook(ctx, result)

        return result


# === Built-in Middleware Hooks ===


async def compression_pre_hook(
    ctx: MiddlewareContext,
    compression: ZstdCompression,
) -> MiddlewareContext:
    """
    Compress data before upload.

    Args:
        ctx: Middleware context.
        compression: Compression instance.

    Returns:
        Modified context with compressed data.
    """

    if ctx.operation in ("upload",):
        if compression.is_available and ctx.data:
            original_size = len(ctx.data)
            ctx.data = compression.compress(ctx.data)
            compressed_size = len(ctx.data)
            ctx.extra["compressed"] = True
            ctx.extra["original_size"] = original_size
            ctx.extra["compressed_size"] = compressed_size
    elif ctx.operation in ("download",):
        if compression.is_available and ctx.data:
            ctx.data = compression.decompress(ctx.data)
            ctx.extra["decompressed"] = True

    return ctx


async def encryption_pre_hook(
    ctx: MiddlewareContext,
    encryption: StorageEncryption,
) -> MiddlewareContext:
    """
    Encrypt data before upload.

    Args:
        ctx: Middleware context.
        encryption: Encryption instance.

    Returns:
        Modified context with encrypted data.
    """

    if ctx.operation in ("upload",):
        if encryption.is_initialized and ctx.data:
            ctx.data = encryption.encrypt(ctx.data)
            ctx.extra["encrypted"] = True
    elif ctx.operation in ("download",):
        if encryption.is_initialized and ctx.data:
            ctx.data = encryption.decrypt(ctx.data)
            ctx.extra["decrypted"] = True

    return ctx


async def cache_pre_hook(
    ctx: MiddlewareContext,
    cache: StorageCache,
    metrics: StorageMetrics,
) -> MiddlewareContext:
    """
    Check cache before operation.

    Args:
        ctx: Middleware context.
        cache: Cache instance.
        metrics: Metrics instance.

    Returns:
        Modified context.
    """

    if ctx.operation in (
        "metadata",
        "exists",
        "list",
    ):
        cached = await cache.get_metadata(ctx.key)
        if cached is not None:
            ctx.extra["cached_result"] = cached
            metrics.record_cache_hit()
        else:
            metrics.record_cache_miss()

    return ctx


async def cache_post_hook(
    ctx: MiddlewareContext,
    result: Any,
    cache: StorageCache,
) -> Any:
    """
    Store result in cache after operation.

    Args:
        ctx: Middleware context.
        result: Operation result.
        cache: Cache instance.

    Returns:
        Unmodified result.
    """

    if ctx.operation in ("upload", "copy", "move"):
        if result and hasattr(result, "to_dict"):
            await cache.set_metadata(ctx.key, result)
    elif ctx.operation in ("delete",):
        await cache.invalidate(ctx.key)

    return result


async def metrics_post_hook(
    ctx: MiddlewareContext,
    result: Any,
    metrics: StorageMetrics,
    start_time: float,
) -> Any:
    """
    Record metrics after operation.

    Args:
        ctx: Middleware context.
        result: Operation result.
        metrics: Metrics instance.
        start_time: Operation start time.

    Returns:
        Unmodified result.
    """

    latency_ms = (perf_counter() - start_time) * 1000

    if ctx.operation == "upload":
        metrics.record_upload(
            size=ctx.extra.get(
                "original_size",
                len(ctx.data) if ctx.data else 0,
            ),
            latency_ms=latency_ms,
        )
    elif ctx.operation == "download":
        metrics.record_download(
            size=len(result) if result else 0,
            latency_ms=latency_ms,
        )
    elif ctx.operation == "delete":
        metrics.record_delete(latency_ms)
    elif ctx.operation == "copy":
        metrics.record_copy(latency_ms)
    elif ctx.operation == "move":
        metrics.record_move(latency_ms)

    return result