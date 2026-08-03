"""
Storage tracing hooks.

Provides OpenTelemetry-compatible tracing for
storage operations, enabling distributed
tracing across the ICYQuant platform.
"""

from __future__ import annotations

from typing import Any, Optional


class StorageTracing:
    """
    Storage tracing hooks.

    Provides before/after hooks for storage
    operations to integrate with OpenTelemetry
    distributed tracing.

    Hooks can be connected to:
    - OpenTelemetry span creation
    - Structured logging
    - Audit trail recording
    - Performance profiling

    Usage:
        tracing = StorageTracing()
        tracing.set_tracer(my_tracer)

        await tracing.before_upload(key)
        result = await service.upload(key, data)
        await tracing.after_upload(key)
    """

    def __init__(
        self,
        service_name: str = "icyquant.storage",
    ) -> None:
        """
        Initialize tracing hooks.

        Args:
            service_name: Service name for tracer.
        """

        self._service_name = service_name
        self._tracer: Any = None
        self._enabled = True

    def set_tracer(
        self,
        tracer: Any,
    ) -> None:
        """
        Set the OpenTelemetry tracer.

        Args:
            tracer: OpenTelemetry tracer instance.
        """

        self._tracer = tracer

    @property
    def is_enabled(self) -> bool:
        """Check if tracing is enabled."""
        return self._enabled

    def enable(self) -> None:
        """Enable tracing."""
        self._enabled = True

    def disable(self) -> None:
        """Disable tracing."""
        self._enabled = False

    async def before_upload(
        self,
        key: str,
        size: Optional[int] = None,
    ) -> None:
        """
        Hook called before upload operation.

        Args:
            key: Object key being uploaded.
            size: Data size in bytes.
        """

        if not self._enabled:
            return

        if self._tracer is not None:
            span = self._tracer.start_span(
                f"storage.upload",
                attributes={
                    "storage.key": key,
                    "storage.operation": "upload",
                    "storage.size_bytes": size or 0,
                },
            )
            span.set_attribute(
                "storage.pipeline", "compress→encrypt→upload"
            )

    async def after_upload(
        self,
        key: str,
        success: bool = True,
        error: Optional[str] = None,
    ) -> None:
        """
        Hook called after upload operation.

        Args:
            key: Object key uploaded.
            success: Whether upload succeeded.
            error: Error message if failed.
        """

        if not self._enabled:
            return

        if self._tracer is not None:
            span = self._tracer.start_span(
                f"storage.upload.result",
                attributes={
                    "storage.key": key,
                    "storage.success": success,
                },
            )
            if error:
                span.set_attribute(
                    "storage.error", error
                )

    async def before_download(
        self,
        key: str,
    ) -> None:
        """
        Hook called before download operation.

        Args:
            key: Object key being downloaded.
        """

        if not self._enabled:
            return

        if self._tracer is not None:
            span = self._tracer.start_span(
                f"storage.download",
                attributes={
                    "storage.key": key,
                    "storage.operation": "download",
                },
            )

    async def after_download(
        self,
        key: str,
        success: bool = True,
        error: Optional[str] = None,
    ) -> None:
        """
        Hook called after download operation.

        Args:
            key: Object key downloaded.
            success: Whether download succeeded.
            error: Error message if failed.
        """

        if not self._enabled:
            return

        if self._tracer is not None:
            span = self._tracer.start_span(
                f"storage.download.result",
                attributes={
                    "storage.key": key,
                    "storage.success": success,
                },
            )
            if error:
                span.set_attribute(
                    "storage.error", error
                )

    async def before_delete(
        self,
        key: str,
    ) -> None:
        """
        Hook called before delete operation.

        Args:
            key: Object key being deleted.
        """

        if not self._enabled:
            return

        if self._tracer is not None:
            span = self._tracer.start_span(
                f"storage.delete",
                attributes={
                    "storage.key": key,
                    "storage.operation": "delete",
                },
            )

    async def after_delete(
        self,
        key: str,
        success: bool = True,
        error: Optional[str] = None,
    ) -> None:
        """
        Hook called after delete operation.

        Args:
            key: Object key deleted.
            success: Whether delete succeeded.
            error: Error message if failed.
        """

        if not self._enabled:
            return

        if self._tracer is not None:
            span = self._tracer.start_span(
                f"storage.delete.result",
                attributes={
                    "storage.key": key,
                    "storage.success": success,
                },
            )
            if error:
                span.set_attribute(
                    "storage.error", error
                )

    async def before_copy(
        self,
        source: str,
        target: str,
    ) -> None:
        """
        Hook called before copy operation.

        Args:
            source: Source object key.
            target: Target object key.
        """

        if not self._enabled:
            return

        if self._tracer is not None:
            span = self._tracer.start_span(
                f"storage.copy",
                attributes={
                    "storage.source": source,
                    "storage.target": target,
                },
            )

    async def after_copy(
        self,
        source: str,
        target: str,
        success: bool = True,
        error: Optional[str] = None,
    ) -> None:
        """
        Hook called after copy operation.

        Args:
            source: Source object key.
            target: Target object key.
            success: Whether copy succeeded.
            error: Error message if failed.
        """

        if not self._enabled:
            return

        if self._tracer is not None:
            span = self._tracer.start_span(
                f"storage.copy.result",
                attributes={
                    "storage.source": source,
                    "storage.target": target,
                    "storage.success": success,
                },
            )
            if error:
                span.set_attribute(
                    "storage.error", error
                )
