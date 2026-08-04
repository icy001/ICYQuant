"""
Configuration platform lifecycle management.

Provides unified lifecycle management for all
configuration platform components:
- Startup
- Reload
- Health Check
- Graceful Shutdown

Lifecycle Flow:
    Startup → Running → (Reload | Health Check) → Shutdown
"""

from __future__ import annotations

import asyncio
import threading
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from .container import DIContainer


class LifecycleState(str, Enum):
    """Configuration platform lifecycle states."""

    CREATED = "created"
    STARTING = "starting"
    RUNNING = "running"
    RELOADING = "reloading"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


class ConfigurationLifecycle:
    """
    Unified lifecycle management.

    Coordinates the startup, reload, and shutdown
    of all configuration platform components.

    Usage:
        lifecycle = ConfigurationLifecycle(container)
        await lifecycle.startup()
        # ... platform running ...
        await lifecycle.reload()
        # ... shutdown ...
        await lifecycle.shutdown()
    """

    def __init__(
        self,
        container: Optional[DIContainer] = None,
    ) -> None:
        """
        Initialize lifecycle manager.

        Args:
            container: DI container with registered components.
        """
        self._container = container or DIContainer()
        self._state = LifecycleState.CREATED
        self._lock = threading.RLock()
        self._startup_hooks: List[Callable] = []
        self._shutdown_hooks: List[Callable] = []
        self._reload_hooks: List[Callable] = []
        self._started_at: Optional[datetime] = None
        self._stopped_at: Optional[datetime] = None

    @property
    def state(
        self,
    ) -> LifecycleState:
        """Get current lifecycle state."""
        return self._state

    @property
    def is_running(
        self,
    ) -> bool:
        """Check if platform is running."""
        return self._state == LifecycleState.RUNNING

    @property
    def container(
        self,
    ) -> DIContainer:
        """Get DI container."""
        return self._container

    def add_startup_hook(
        self,
        hook: Callable,
    ) -> None:
        """Add a startup hook."""
        self._startup_hooks.append(hook)

    def add_shutdown_hook(
        self,
        hook: Callable,
    ) -> None:
        """Add a shutdown hook."""
        self._shutdown_hooks.append(hook)

    def add_reload_hook(
        self,
        hook: Callable,
    ) -> None:
        """Add a reload hook."""
        self._reload_hooks.append(hook)

    async def startup(
        self,
    ) -> Dict[str, Any]:
        """
        Start the configuration platform.

        Executes startup hooks and transitions
        to RUNNING state.

        Returns:
            Startup result.
        """
        with self._lock:
            if self._state not in (LifecycleState.CREATED, LifecycleState.STOPPED):
                return {"success": False, "error": f"Cannot start from state {self._state}"}

            self._state = LifecycleState.STARTING

        try:
            # Run startup hooks
            results = []
            for hook in self._startup_hooks:
                if asyncio.iscoroutinefunction(hook):
                    result = await hook()
                else:
                    result = hook()
                results.append(result)

            self._started_at = datetime.utcnow()
            self._state = LifecycleState.RUNNING

            return {
                "success": True,
                "state": self._state.value,
                "started_at": self._started_at.isoformat(),
                "hooks_executed": len(results),
            }

        except Exception as e:
            self._state = LifecycleState.ERROR
            return {
                "success": False,
                "error": str(e),
                "state": self._state.value,
            }

    async def reload(
        self,
    ) -> Dict[str, Any]:
        """
        Reload the configuration platform.

        Returns:
            Reload result.
        """
        with self._lock:
            if self._state != LifecycleState.RUNNING:
                return {"success": False, "error": f"Cannot reload from state {self._state}"}

            self._state = LifecycleState.RELOADING

        try:
            results = []
            for hook in self._reload_hooks:
                if asyncio.iscoroutinefunction(hook):
                    result = await hook()
                else:
                    result = hook()
                results.append(result)

            self._state = LifecycleState.RUNNING

            return {
                "success": True,
                "state": self._state.value,
                "hooks_executed": len(results),
            }

        except Exception as e:
            self._state = LifecycleState.ERROR
            return {
                "success": False,
                "error": str(e),
            }

    async def shutdown(
        self,
        timeout: float = 30.0,
    ) -> Dict[str, Any]:
        """
        Gracefully shut down the platform.

        Args:
            timeout: Maximum shutdown time.

        Returns:
            Shutdown result.
        """
        with self._lock:
            if self._state == LifecycleState.STOPPED:
                return {"success": True, "state": "already_stopped"}

            self._state = LifecycleState.STOPPING

        try:
            # Run shutdown hooks in reverse order
            results = []
            for hook in reversed(self._shutdown_hooks):
                try:
                    if asyncio.iscoroutinefunction(hook):
                        result = await asyncio.wait_for(hook(), timeout=timeout)
                    else:
                        result = hook()
                    results.append(result)
                except asyncio.TimeoutError:
                    pass
                except Exception:
                    pass

            self._stopped_at = datetime.utcnow()
            self._state = LifecycleState.STOPPED

            return {
                "success": True,
                "state": self._state.value,
                "stopped_at": self._stopped_at.isoformat(),
                "hooks_executed": len(results),
            }

        except Exception as e:
            self._state = LifecycleState.ERROR
            return {
                "success": False,
                "error": str(e),
            }

    def get_status(
        self,
    ) -> Dict[str, Any]:
        """Get lifecycle status."""
        return {
            "state": self._state.value,
            "is_running": self.is_running,
            "started_at": self._started_at.isoformat() if self._started_at else None,
            "stopped_at": self._stopped_at.isoformat() if self._stopped_at else None,
            "startup_hooks": len(self._startup_hooks),
            "shutdown_hooks": len(self._shutdown_hooks),
            "reload_hooks": len(self._reload_hooks),
            "registrations": self._container.list_registrations(),
        }
