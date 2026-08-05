from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

from .configuration import ConfigurationManager
from .marketplace.marketplace import PluginMarketplace
from .registry import PluginRegistry
from .loader.loader import PluginLoader
from .sandbox.sandbox import Sandbox
from .events import PluginEvent, PluginEventBus, PluginEventType
from .manager import PluginManager
from .runtime import PluginRuntime
from .runtime_context import RuntimeContext
from .platform import PluginPlatform
from .container import Container
from .lifecycle import PluginLifecycle
from .dependency import DependencyResolver
from .exceptions import PluginError

logger = logging.getLogger(__name__)


class PluginBootstrap:
    """Unified bootstrap entry point for the plugin framework.

    Orchestrates the full startup and shutdown sequence, wiring
    together all sub-systems in the correct dependency order.

    Startup order::

        Configuration → Marketplace → Registry → Dependencies
        → Sandbox → Runtime → Sync → Application

    Shutdown order::

        Stop scheduler → Stop all plugins → Persist snapshot
        → Flush events → Shutdown runtime

    Usage::

        bootstrap = PluginBootstrap()
        await bootstrap.startup()
        platform = bootstrap.get_platform()
        await platform.start("my_plugin")
        await bootstrap.shutdown()
    """

    def __init__(self) -> None:
        self._container = Container()
        self._config = ConfigurationManager()
        self._marketplace = PluginMarketplace()
        self._registry = PluginRegistry()
        self._loader = PluginLoader(registry=self._registry)
        self._sandbox = Sandbox()
        self._event_bus = PluginEventBus()
        self._lifecycle = PluginLifecycle()
        self._resolver = DependencyResolver()
        self._manager = PluginManager()
        self._runtime = PluginRuntime(
            registry=self._registry,
            loader=self._loader,
            sandbox=self._sandbox,
            event_bus=self._event_bus,
        )
        self._platform = PluginPlatform(
            registry=self._registry,
            loader=self._loader,
            sandbox=self._sandbox,
            marketplace=self._marketplace,
            lifecycle=self._lifecycle,
            manager=self._manager,
            runtime=self._runtime,
            event_bus=self._event_bus,
        )

        self._initialized = False
        self._startup_started = False
        self._shutdown_started = False
        self._startup_time: Optional[float] = None

    async def startup(self) -> None:
        """Execute the full startup sequence.

        Steps:
        1. Initialize configuration platform
        2. Initialize plugin marketplace
        3. Initialize plugin registry
        4. Resolve dependencies
        5. Initialize sandbox runtime
        6. Initialize plugin runtime
        7. Initialize cluster synchronization
        8. Emit startup complete event
        """
        if self._startup_started:
            logger.debug("Bootstrap startup already in progress.")
            return
        self._startup_started = True
        self._startup_time = time.monotonic()

        logger.info("=== Plugin Framework Bootstrap Starting ===")

        try:
            logger.info("[1/8] Initializing configuration platform.")
            self._initialize_configuration()

            logger.info("[2/8] Initializing plugin marketplace.")
            await self._initialize_marketplace()

            logger.info("[3/8] Initializing plugin registry.")
            self._initialize_registry()

            logger.info("[4/8] Resolving dependencies.")
            self._resolve_dependencies()

            logger.info("[5/8] Initializing sandbox runtime.")
            self._initialize_sandbox()

            logger.info("[6/8] Initializing plugin runtime.")
            self._initialize_runtime()

            logger.info("[7/8] Initializing cluster synchronization.")
            self._initialize_cluster_sync()

            logger.info("[8/8] Emitting startup complete event.")
            await self._emit_startup_complete()

            self._initialized = True
            elapsed = time.monotonic() - (self._startup_time or time.monotonic())
            logger.info(
                "=== Plugin Framework Bootstrap Complete (%.3fs) ===", elapsed
            )
        except Exception as e:
            logger.error("Bootstrap startup failed: %s", e)
            self._startup_started = False
            raise PluginError(
                f"Bootstrap startup failed: {e}"
            ) from e

    async def shutdown(self) -> None:
        """Execute the graceful shutdown sequence.

        Steps:
        1. Stop scheduler
        2. Stop all plugins
        3. Persist snapshot
        4. Flush events
        5. Shutdown runtime
        """
        if self._shutdown_started:
            return
        self._shutdown_started = True

        logger.info("=== Plugin Framework Bootstrap Shutting Down ===")

        try:
            logger.info("[1/5] Stopping scheduler.")
            self._stop_scheduler()

            logger.info("[2/5] Stopping all plugins.")
            await self._stop_all_plugins()

            logger.info("[3/5] Persisting snapshot.")
            self._persist_snapshot()

            logger.info("[4/5] Flushing events.")
            await self._flush_events()

            logger.info("[5/5] Shutting down runtime.")
            await self._shutdown_runtime()

            self._initialized = False
            logger.info("=== Plugin Framework Bootstrap Shutdown Complete ===")
        except Exception as e:
            logger.error("Bootstrap shutdown error: %s", e)
        finally:
            self._shutdown_started = False

    async def initialize(self) -> None:
        """Alias for :meth:`startup`."""
        await self.startup()

    def get_platform(self) -> PluginPlatform:
        """Return the unified plugin platform.

        Returns:
            The :class:`PluginPlatform` instance.
        """
        return self._platform

    def get_runtime(self) -> PluginRuntime:
        """Return the plugin runtime.

        Returns:
            The :class:`PluginRuntime` instance.
        """
        return self._runtime

    def get_container(self) -> Container:
        """Return the dependency injection container.

        Returns:
            The :class:`Container` instance.
        """
        return self._container

    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive bootstrap and platform statistics.

        Returns:
            A dictionary with stats from all sub-systems.
        """
        return {
            "initialized": self._initialized,
            "startup_duration": (
                time.monotonic() - self._startup_time
                if self._startup_time
                else 0.0
            ),
            "container": self._container.get_stats(),
            "platform": self._platform.get_stats(),
            "runtime": self._runtime.get_runtime_stats(),
            "marketplace": self._marketplace.get_stats(),
            "registry": self._registry.get_stats(),
            "sandbox": self._sandbox.get_stats(),
        }

    def _initialize_configuration(self) -> None:
        """Step 1: Initialize configuration platform and register
        core services in the DI container."""
        self._container.register_singleton(ConfigurationManager, self._config)
        self._container.register_singleton(PluginRegistry, self._registry)
        self._container.register_singleton(PluginLoader, self._loader)
        self._container.register_singleton(Sandbox, self._sandbox)
        self._container.register_singleton(PluginEventBus, self._event_bus)
        self._container.register_singleton(PluginLifecycle, self._lifecycle)
        self._container.register_singleton(DependencyResolver, self._resolver)
        self._container.register_singleton(PluginManager, self._manager)
        self._container.register_singleton(
            PluginMarketplace, self._marketplace
        )
        self._container.register_singleton(PluginRuntime, self._runtime)
        self._container.register_singleton(PluginPlatform, self._platform)
        self._container.register_singleton(Container, self._container)
        logger.debug("Configuration platform initialized.")

    async def _initialize_marketplace(self) -> None:
        """Step 2: Connect to repositories and sync the marketplace."""
        try:
            await self._marketplace.initialize()
        except Exception as e:
            logger.warning("Marketplace initialization had issues: %s", e)
            logger.warning("Continuing with degraded marketplace state.")

    def _initialize_registry(self) -> None:
        """Step 3: Initialize the plugin registry (already created)."""
        logger.debug(
            "Registry initialized with %d plugins.",
            self._registry.count(),
        )

    def _resolve_dependencies(self) -> None:
        """Step 4: Resolve inter-plugin dependencies."""
        all_plugins = self._registry.get_all()
        if not all_plugins:
            logger.debug("No plugins registered; skipping dependency resolution.")
            return

        graph: Dict[str, list] = {}
        available: set[str] = set()
        for plugin in all_plugins:
            graph[plugin.id] = list(plugin.dependencies)
            available.add(plugin.id)

        resolution = self._resolver.resolve(graph, available)
        order = resolution.get("order", [])
        cycles = resolution.get("cycles", [])
        missing = resolution.get("missing", {})

        if cycles:
            logger.warning(
                "Circular dependencies detected: %s", cycles
            )
        if missing:
            logger.warning(
                "Missing dependencies detected: %s", missing
            )

        logger.info(
            "Dependency resolution complete. Load order: %s", order
        )

    def _initialize_sandbox(self) -> None:
        """Step 5: Initialize sandbox runtime for isolation."""
        logger.debug("Sandbox runtime initialized.")

    def _initialize_runtime(self) -> None:
        """Step 6: Initialize plugin runtime and register with container."""
        logger.debug("Plugin runtime initialized.")

    def _initialize_cluster_sync(self) -> None:
        """Step 7: Initialize cluster synchronization.

        This is a placeholder for future multi-node coordination.
        When cluster sync is implemented, this method will connect
        to a distributed state store and synchronize plugin state
        across nodes.
        """
        logger.debug("Cluster sync placeholder (single-node mode).")

    async def _emit_startup_complete(self) -> None:
        """Step 8: Emit startup complete event through the event bus."""
        event = PluginEvent(
            event_type="framework.startup_complete",
            plugin_id="bootstrap",
            data={
                "timestamp": time.monotonic(),
                "platform_stats": self._platform.get_stats(),
            },
        )
        await self._event_bus.publish(event)
        logger.debug("Startup complete event emitted.")

    def _stop_scheduler(self) -> None:
        """Shutdown step 1: Stop any running scheduler tasks."""
        logger.debug("Scheduler stop requested (no-op by default).")

    async def _stop_all_plugins(self) -> None:
        """Shutdown step 2: Stop all active plugins through the runtime."""
        active = self._runtime.get_active_plugins()
        if not active:
            logger.debug("No active plugins to stop.")
            return

        logger.info("Stopping %d active plugins.", len(active))
        for plugin_id in active:
            try:
                await self._runtime.stop_plugin(plugin_id)
            except Exception as e:
                logger.error(
                    "Error stopping '%s' during shutdown: %s",
                    plugin_id,
                    e,
                )

    def _persist_snapshot(self) -> None:
        """Shutdown step 3: Persist a snapshot of the plugin state."""
        try:
            snapshot = self._platform.get_stats()
            logger.debug("Platform snapshot: %s", snapshot)
        except Exception as e:
            logger.error("Failed to persist snapshot: %s", e)

    async def _flush_events(self) -> None:
        """Shutdown step 4: Flush remaining events through the event bus."""
        try:
            history = self._event_bus.get_history(limit=0)
            if history:
                logger.debug(
                    "Flushing %d remaining events.", len(history)
                )
        except Exception as e:
            logger.error("Failed to flush events: %s", e)

    async def _shutdown_runtime(self) -> None:
        """Shutdown step 5: Shut down runtime and all sub-systems."""
        try:
            await self._sandbox.shutdown()
        except Exception as e:
            logger.error("Error shutting down sandbox: %s", e)

        try:
            await self._manager.shutdown()
        except Exception as e:
            logger.error("Error shutting down manager: %s", e)

        try:
            await self._marketplace.shutdown()
        except Exception as e:
            logger.error("Error shutting down marketplace: %s", e)

        try:
            self._registry.clear()
        except Exception as e:
            logger.error("Error clearing registry: %s", e)