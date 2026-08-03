"""
Logging lifecycle management.

Provides ordered startup and shutdown
sequences for the logging platform,
ensuring proper resource initialization
and cleanup.

Startup order:
    Config → Handlers → Queue → Dispatcher → Worker → Scheduler

Shutdown order:
    Scheduler → Worker → Flush Queue → Handlers
"""

from __future__ import annotations

import asyncio
from typing import Any, Callable, List, Optional

from .config import LoggingConfig
from .handlers import LogHandler


class LoggingLifecycle:
    """
    Logging lifecycle manager.

    Coordinates the startup and shutdown
    of logging components in the correct
    order, with hook support for custom
    initialization and cleanup.

    Features:
    - Ordered startup/shutdown
    - Pre/post hooks
    - Error recovery
    - Timeout support

    Usage:
        lifecycle = LoggingLifecycle(
            on_startup=my_init,
            on_shutdown=my_cleanup,
        )
        await lifecycle.startup()
        # ... running ...
        await lifecycle.shutdown()
    """

    def __init__(
        self,
        on_startup: Optional[Callable] = None,
        on_shutdown: Optional[Callable] = None,
        startup_timeout: float = 30.0,
        shutdown_timeout: float = 10.0,
    ) -> None:
        """
        Initialize lifecycle manager.

        Args:
            on_startup: Optional async startup hook.
            on_shutdown: Optional async shutdown hook.
            startup_timeout: Max startup time in seconds.
            shutdown_timeout: Max shutdown time in seconds.
        """

        self._on_startup = on_startup
        self._on_shutdown = on_shutdown
        self._startup_timeout = startup_timeout
        self._shutdown_timeout = shutdown_timeout
        self._started: bool = False
        self._startup_hooks: List[Callable] = []
        self._shutdown_hooks: List[Callable] = []

    @property
    def is_started(
        self,
    ) -> bool:
        """Check if lifecycle is started."""
        return self._started

    def add_startup_hook(
        self,
        hook: Callable,
    ) -> None:
        """
        Add a startup hook.

        Args:
            hook: Async callable to run on startup.
        """

        self._startup_hooks.append(hook)

    def add_shutdown_hook(
        self,
        hook: Callable,
    ) -> None:
        """
        Add a shutdown hook.

        Args:
            hook: Async callable to run on shutdown.
        """

        self._shutdown_hooks.append(hook)

    async def startup(
        self,
    ) -> None:
        """
        Execute startup sequence.

        Runs pre-startup hooks, main startup
        callback, then post-startup hooks.
        """

        if self._started:
            return

        # Run startup hooks
        for hook in self._startup_hooks:
            try:
                result = hook()
                if asyncio.iscoroutine(result):
                    await asyncio.wait_for(
                        result,
                        timeout=self._startup_timeout,
                    )
            except asyncio.TimeoutError:
                pass
            except Exception:
                pass

        # Run main startup
        if self._on_startup is not None:
            result = self._on_startup()
            if asyncio.iscoroutine(result):
                await asyncio.wait_for(
                    result,
                    timeout=self._startup_timeout,
                )

        self._started = True

    async def shutdown(
        self,
    ) -> None:
        """
        Execute shutdown sequence.

        Runs pre-shutdown hooks, main shutdown
        callback, then post-shutdown hooks.
        """

        if not self._started:
            return

        # Run main shutdown
        if self._on_shutdown is not None:
            try:
                result = self._on_shutdown()
                if asyncio.iscoroutine(result):
                    await asyncio.wait_for(
                        result,
                        timeout=self._shutdown_timeout,
                    )
            except asyncio.TimeoutError:
                pass
            except Exception:
                pass

        # Run shutdown hooks (reverse order)
        for hook in reversed(self._shutdown_hooks):
            try:
                result = hook()
                if asyncio.iscoroutine(result):
                    await asyncio.wait_for(
                        result,
                        timeout=self._shutdown_timeout,
                    )
            except asyncio.TimeoutError:
                pass
            except Exception:
                pass

        self._started = False

    def get_status(
        self,
    ) -> dict:
        """Get lifecycle status."""

        return {
            "started": self._started,
            "startup_hooks": len(self._startup_hooks),
            "shutdown_hooks": len(self._shutdown_hooks),
        }
