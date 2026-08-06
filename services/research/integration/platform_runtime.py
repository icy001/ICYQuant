"""Platform Runtime — unified lifecycle and state management for the research platform.

Commit 11 Part 1.5: Manages platform initialization sequence, dependency resolution,
state machine, and graceful shutdown coordination.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class PlatformRuntimeState(str, Enum):
    """Platform runtime lifecycle states."""

    CREATED = "created"
    INITIALIZING = "initializing"
    READY = "ready"
    RUNNING = "running"
    PAUSED = "paused"
    SHUTTING_DOWN = "shutting_down"
    TERMINATED = "terminated"
    ERROR = "error"


class PlatformRuntime:
    """Unified research platform runtime.

    Manages the platform lifecycle: initialization ordering, dependency
    resolution, component registration, state transitions, and graceful shutdown.

    Usage::

        runtime = PlatformRuntime(config={"name": "research-platform"})
        await runtime.initialize()
        await runtime.register_component("workflow", workflow_adapter)
        await runtime.start()
        # ... platform running ...
        await runtime.shutdown()
    """

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        *,
        runtime_id: Optional[str] = None,
    ) -> None:
        self._id: str = runtime_id or f"prt-{uuid4().hex[:12]}"
        self._config: Dict[str, Any] = config or {}
        self._state: PlatformRuntimeState = PlatformRuntimeState.CREATED
        self._created_at: datetime = datetime.now(timezone.utc)
        self._started_at: Optional[datetime] = None

        # Component registry
        self._components: Dict[str, Any] = {}
        self._component_status: Dict[str, str] = {}
        self._init_hooks: List[Callable] = []
        self._shutdown_hooks: List[Callable] = []

        # Platform metadata
        self._version: str = self._config.get("version", "1.0.0")
        self._environment: str = self._config.get("environment", "development")

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def id(self) -> str:
        return self._id

    @property
    def state(self) -> PlatformRuntimeState:
        return self._state

    @property
    def version(self) -> str:
        return self._version

    @property
    def environment(self) -> str:
        return self._environment

    @property
    def components(self) -> Dict[str, Any]:
        return dict(self._components)

    @property
    def is_ready(self) -> bool:
        return self._state in (PlatformRuntimeState.READY, PlatformRuntimeState.RUNNING)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """Initialize the platform runtime."""
        if self._state != PlatformRuntimeState.CREATED:
            logger.warning("PlatformRuntime already initialized (state=%s)", self._state.value)
            return

        self._state = PlatformRuntimeState.INITIALIZING
        logger.info("Initializing PlatformRuntime [%s] v%s (%s)", self._id, self._version, self._environment)

        # Execute initialization hooks
        for hook in self._init_hooks:
            try:
                if asyncio.iscoroutinefunction(hook):
                    await hook(self)
                else:
                    hook(self)
            except Exception as exc:
                logger.error("Init hook failed: %s", exc, exc_info=True)

        self._state = PlatformRuntimeState.READY
        logger.info("PlatformRuntime initialized [%s]", self._id)

    async def start(self) -> None:
        """Start the platform runtime — transition to RUNNING state."""
        if self._state not in (PlatformRuntimeState.READY, PlatformRuntimeState.PAUSED):
            raise RuntimeError(f"Cannot start from state: {self._state.value}")

        self._state = PlatformRuntimeState.RUNNING
        self._started_at = datetime.now(timezone.utc)
        logger.info("PlatformRuntime started [%s]", self._id)

    async def pause(self) -> None:
        """Pause platform operations."""
        if self._state != PlatformRuntimeState.RUNNING:
            raise RuntimeError(f"Cannot pause from state: {self._state.value}")
        self._state = PlatformRuntimeState.PAUSED
        logger.info("PlatformRuntime paused [%s]", self._id)

    async def resume(self) -> None:
        """Resume platform operations from paused state."""
        await self.start()

    async def shutdown(self) -> None:
        """Gracefully shutdown the platform runtime."""
        if self._state in (PlatformRuntimeState.TERMINATED, PlatformRuntimeState.CREATED):
            return

        self._state = PlatformRuntimeState.SHUTTING_DOWN
        logger.info("Shutting down PlatformRuntime [%s]...", self._id)

        # Execute shutdown hooks in reverse order
        for hook in reversed(self._shutdown_hooks):
            try:
                if asyncio.iscoroutinefunction(hook):
                    await hook(self)
                else:
                    hook(self)
            except Exception as exc:
                logger.error("Shutdown hook failed: %s", exc, exc_info=True)

        self._components.clear()
        self._state = PlatformRuntimeState.TERMINATED
        logger.info("PlatformRuntime terminated [%s]", self._id)

    # ------------------------------------------------------------------
    # Component Management
    # ------------------------------------------------------------------

    async def register_component(self, name: str, component: Any, *, dependencies: Optional[List[str]] = None) -> None:
        """Register a platform component.

        Args:
            name: Unique component name.
            component: The component instance.
            dependencies: Optional list of component names this depends on.
        """
        if name in self._components:
            logger.warning("Component already registered: %s", name)
            return

        # Validate dependencies
        if dependencies:
            for dep in dependencies:
                if dep not in self._components:
                    raise RuntimeError(f"Dependency '{dep}' not registered for component '{name}'")

        self._components[name] = component
        self._component_status[name] = "registered"
        logger.info("Component registered: %s", name)

    async def unregister_component(self, name: str) -> None:
        """Unregister a platform component."""
        if name not in self._components:
            return
        del self._components[name]
        self._component_status.pop(name, None)
        logger.info("Component unregistered: %s", name)

    def get_component(self, name: str) -> Any:
        """Get a registered component by name."""
        component = self._components.get(name)
        if component is None:
            raise KeyError(f"Component not found: {name}")
        return component

    def add_init_hook(self, hook: Callable) -> None:
        """Register an initialization hook."""
        self._init_hooks.append(hook)

    def add_shutdown_hook(self, hook: Callable) -> None:
        """Register a shutdown hook."""
        self._shutdown_hooks.append(hook)

    # ------------------------------------------------------------------
    # Status / Diagnostics
    # ------------------------------------------------------------------

    async def status(self) -> Dict[str, Any]:
        """Return platform runtime status."""
        return {
            "runtime_id": self._id,
            "state": self._state.value,
            "version": self._version,
            "environment": self._environment,
            "created_at": self._created_at.isoformat(),
            "started_at": self._started_at.isoformat() if self._started_at else None,
            "component_count": len(self._components),
            "components": dict(self._component_status),
        }
