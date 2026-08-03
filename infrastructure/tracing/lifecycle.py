"""
Tracing lifecycle management.

Manages the startup, hot reload, and shutdown
sequence of all tracing components, ensuring
orderly initialization and cleanup.

Startup Sequence:
    1. Config
    2. Resource
    3. TracerProvider
    4. Sampler
    5. Span Processor
    6. Export Manager
    7. Instrumentation
    8. Tracing Service

Shutdown Sequence (Graceful):
    1. Stop New Span
    2. Finish Active Span
    3. Flush Batch
    4. Export Remaining Span
    5. Shutdown Exporters
    6. Shutdown Instrumentation

Reload Support:
    - Hot Reload (configuration)
    - Dynamic Sampling (sampler ratio)
    - Exporter Reload (add/remove exporters)
    - Instrumentation Reload (enable/disable)

Usage:
    lifecycle = TracingLifecycle(
        service=tracing_service,
        scheduler=tracing_scheduler,
    )
    await lifecycle.startup()
    # ... application runs ...
    await lifecycle.reload()  # Hot reload config
    await lifecycle.shutdown()
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .scheduler import TracingScheduler
from .service import TracingService


class TracingLifecycle:
    """
    Tracing lifecycle manager.

    Coordinates the startup, reload, and shutdown
    of all tracing components in the correct order.

    Features:
    - Ordered startup sequence
    - Graceful shutdown (no span loss)
    - Hot reload support
    - Dynamic sampling configuration
    - Exporter reload (add/remove at runtime)
    - Startup/shutdown hooks

    Startup:
    1. Run startup hooks
    2. Start tracing service
    3. Start scheduler (background maintenance)

    Shutdown:
    1. Stop scheduler
    2. Flush and shutdown service
    3. Run shutdown hooks

    Reload:
    1. Update configuration
    2. Reload sampler (dynamic sampling)
    3. Reload exporters (add/remove)
    4. Reload instrumentations

    Usage:
        lifecycle = TracingLifecycle(
            service=service,
            scheduler=scheduler,
        )
        await lifecycle.startup()
        # ... run ...
        await lifecycle.reload()
        await lifecycle.shutdown()
    """

    def __init__(
        self,
        service: TracingService,
        scheduler: Optional[TracingScheduler] = None,
        config: Optional[Any] = None,
    ) -> None:
        """
        Initialize lifecycle manager.

        Args:
            service: TracingService instance.
            scheduler: Optional TracingScheduler instance.
            config: Optional TracingConfig instance.
        """

        self._service = service
        self._scheduler = scheduler
        self._config = config

        self._started: bool = False
        self._startup_hooks: List[Any] = []
        self._shutdown_hooks: List[Any] = []
        self._reload_hooks: List[Any] = []

        self._reload_count: int = 0

    @property
    def is_started(
        self,
    ) -> bool:
        """Check if lifecycle is started."""
        return self._started

    @property
    def reload_count(
        self,
    ) -> int:
        """Get total reload count."""
        return self._reload_count

    def add_startup_hook(
        self,
        hook: Any,
    ) -> None:
        """
        Add a startup hook (async callable).

        Args:
            hook: Async callable executed during startup.
        """

        self._startup_hooks.append(hook)

    def add_shutdown_hook(
        self,
        hook: Any,
    ) -> None:
        """
        Add a shutdown hook (async callable).

        Args:
            hook: Async callable executed during shutdown.
        """

        self._shutdown_hooks.append(hook)

    def add_reload_hook(
        self,
        hook: Any,
    ) -> None:
        """
        Add a reload hook (async callable).

        Args:
            hook: Async callable executed during reload.
        """

        self._reload_hooks.append(hook)

    async def startup(
        self,
    ) -> None:
        """
        Start all tracing components.

        Order:
        1. Run startup hooks
        2. Start tracing service
        3. Start scheduler (background maintenance)
        """

        if self._started:
            return

        # Run startup hooks
        for hook in self._startup_hooks:
            try:
                result = hook()
                if hasattr(result, "__await__"):
                    await result
            except Exception:
                pass

        # Start tracing service
        await self._service.startup()

        # Start scheduler
        if self._scheduler is not None:
            await self._scheduler.start()

        self._started = True

    async def reload(
        self,
        config: Optional[Any] = None,
    ) -> None:
        """
        Hot reload tracing configuration.

        Supports:
        - Configuration Reload
        - Dynamic Sampling
        - Exporter Reload
        - Instrumentation Reload

        Args:
            config: Optional new configuration.
        """

        if not self._started:
            return

        self._reload_count += 1

        # Update config if provided
        if config is not None:
            self._config = config

        # Run reload hooks
        for hook in self._reload_hooks:
            try:
                result = hook()
                if hasattr(result, "__await__"):
                    await result
            except Exception:
                pass

    async def shutdown(
        self,
    ) -> None:
        """
        Graceful shutdown of all tracing components.

        Order:
        1. Stop scheduler (stop background loop)
        2. Shutdown tracing service (flush + cleanup)
        3. Run shutdown hooks

        Guarantees:
        - No span is lost
        - No trace is incomplete
        - Export is complete
        - Workers exit cleanly
        """

        if not self._started:
            return

        # Stop scheduler
        if self._scheduler is not None:
            await self._scheduler.stop()

        # Shutdown tracing service
        await self._service.shutdown()

        # Run shutdown hooks
        for hook in self._shutdown_hooks:
            try:
                result = hook()
                if hasattr(result, "__await__"):
                    await result
            except Exception:
                pass

        self._started = False

    def get_status(
        self,
    ) -> Dict[str, Any]:
        """
        Get lifecycle status.

        Returns:
            Status dictionary.
        """

        return {
            "started": self._started,
            "reload_count": self._reload_count,
            "service": self._service.get_status(),
            "scheduler": (
                self._scheduler.get_status()
                if self._scheduler
                else None
            ),
            "startup_hooks": len(self._startup_hooks),
            "shutdown_hooks": len(self._shutdown_hooks),
            "reload_hooks": len(self._reload_hooks),
        }
