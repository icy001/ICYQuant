"""
Feature flag platform lifecycle management.

Provides startup and shutdown lifecycle
management for the feature flag platform,
ensuring proper initialization order
and graceful shutdown.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class LifecycleState:
    """Platform lifecycle states."""

    INITIALIZING = "initializing"
    STARTED = "started"
    SHUTTING_DOWN = "shutting_down"
    STOPPED = "stopped"
    ERROR = "error"


class PlatformLifecycle:
    """
    Manages feature flag platform lifecycle.

    Provides ordered startup and shutdown
    with hooks for each phase.

    Startup Order:
        1. Configuration Platform
        2. Feature Registry
        3. Targeting Engine
        4. Rollout Engine
        5. Canary Engine
        6. Experiment Engine
        7. Runtime Service
        8. Scheduler
        9. Health Checks

    Shutdown Order (reverse):
        1. Stop Scheduler
        2. Complete Active Experiments
        3. Persist Snapshot
        4. Flush Audit Events
        5. Shutdown Runtime
        6. Shutdown Engines

    Usage:
        lifecycle = PlatformLifecycle()
        lifecycle.add_startup_hook("config", init_config)
        await lifecycle.start()
        await lifecycle.shutdown()
    """

    def __init__(self) -> None:
        self._state = LifecycleState.STOPPED
        self._startup_hooks: List[tuple] = []  # (name, order, coro)
        self._shutdown_hooks: List[tuple] = []  # (name, order, coro)
        self._startup_errors: List[str] = []
        self._shutdown_errors: List[str] = []

    @property
    def state(self) -> str:
        """Get current lifecycle state."""
        return self._state

    def add_startup_hook(
        self,
        name: str,
        coro: Callable,
        order: int = 0,
    ) -> None:
        """
        Add a startup hook.

        Args:
            name: Hook name (for ordering).
            coro: Async coroutine to execute.
            order: Execution order (lower = earlier).
        """
        self._startup_hooks.append((name, order, coro))
        # Sort by order
        self._startup_hooks.sort(key=lambda x: x[1])

    def add_shutdown_hook(
        self,
        name: str,
        coro: Callable,
        order: int = 0,
    ) -> None:
        """
        Add a shutdown hook.

        Args:
            name: Hook name (for ordering).
            coro: Async coroutine to execute.
            order: Execution order (lower = earlier).
        """
        self._shutdown_hooks.append((name, order, coro))
        # Sort by order
        self._shutdown_hooks.sort(key=lambda x: x[1])

    async def start(self) -> None:
        """
        Execute all startup hooks in order.

        Hooks are executed sequentially in the
        order they were added. If any hook fails,
        the platform enters ERROR state.
        """
        self._state = LifecycleState.INITIALIZING
        self._startup_errors = []

        logger.info(
            "Starting platform: %d startup hooks",
            len(self._startup_hooks),
        )

        for name, order, coro in self._startup_hooks:
            try:
                logger.debug(
                    "Startup hook: %s (order=%d)", name, order,
                )
                result = coro()
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.error(
                    "Startup hook '%s' failed: %s", name, e,
                )
                self._startup_errors.append(f"{name}: {e}")
                self._state = LifecycleState.ERROR
                raise

        self._state = LifecycleState.STARTED
        logger.info("Platform started successfully")

    async def shutdown(self) -> None:
        """
        Execute all shutdown hooks in reverse order.

        Ensures graceful shutdown with proper
        ordering and error isolation.
        """
        self._state = LifecycleState.SHUTTING_DOWN
        self._shutdown_errors = []

        logger.info(
            "Shutting down platform: %d shutdown hooks",
            len(self._shutdown_hooks),
        )

        # Execute in reverse order
        for name, order, coro in reversed(self._shutdown_hooks):
            try:
                logger.debug(
                    "Shutdown hook: %s (order=%d)", name, order,
                )
                result = coro()
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.error(
                    "Shutdown hook '%s' failed: %s", name, e,
                )
                self._shutdown_errors.append(f"{name}: {e}")

        self._state = LifecycleState.STOPPED
        logger.info(
            "Platform stopped (%d shutdown errors)",
            len(self._shutdown_errors),
        )

    def get_stats(self) -> Dict[str, Any]:
        """Get lifecycle statistics."""
        return {
            "state": self._state,
            "startup_hooks": len(self._startup_hooks),
            "shutdown_hooks": len(self._shutdown_hooks),
            "startup_errors": self._startup_errors,
            "shutdown_errors": self._shutdown_errors,
        }
