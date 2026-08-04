"""
Configuration bootstrap.

Provides the unified initialization sequence for
the entire configuration platform.

Startup Order:
    Configuration Loader
        ↓
    Environment Manager
        ↓
    Resolver
        ↓
    Registry
        ↓
    Snapshot Manager
        ↓
    Dynamic Configuration
        ↓
    Watcher
        ↓
    Configuration Service
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from .container import DIContainer, create_default_container
from .lifecycle import ConfigurationLifecycle, LifecycleState

logger = logging.getLogger(__name__)


class ConfigurationBootstrap:
    """
    Configuration platform bootstrap.

    Orchestrates the full startup sequence for the
    configuration platform, ensuring correct
    initialization order and dependency resolution.

    Usage:
        bootstrap = ConfigurationBootstrap()
        result = await bootstrap.startup()
        # ... platform running ...
        await bootstrap.shutdown()
    """

    def __init__(
        self,
        container: Optional[DIContainer] = None,
        config_files: Optional[List[str]] = None,
        watch_files: Optional[List[str]] = None,
        enable_watcher: bool = True,
        enable_scheduler: bool = False,
    ) -> None:
        """
        Initialize bootstrap.

        Args:
            container: Custom DI container.
            config_files: Configuration files to load.
            watch_files: Files to watch for changes.
            enable_watcher: Enable file watching.
            enable_scheduler: Enable scheduled reload.
        """
        self._container = container or create_default_container()
        self._lifecycle = ConfigurationLifecycle(self._container)
        self._config_files = config_files or []
        self._watch_files = watch_files or []
        self._enable_watcher = enable_watcher
        self._enable_scheduler = enable_scheduler
        self._components: Dict[str, Any] = {}
        self._startup_log: List[Dict[str, Any]] = []

    @property
    def lifecycle(
        self,
    ) -> ConfigurationLifecycle:
        """Get lifecycle manager."""
        return self._lifecycle

    @property
    def container(
        self,
    ) -> DIContainer:
        """Get DI container."""
        return self._container

    @property
    def startup_log(
        self,
    ) -> List[Dict[str, Any]]:
        """Get startup log."""
        return list(self._startup_log)

    async def startup(
        self,
    ) -> Dict[str, Any]:
        """
        Execute the full startup sequence.

        Returns:
            Startup result with component status.
        """
        self._startup_log.clear()

        # Step 1: Configuration Manager
        await self._init_step("configuration_manager", self._init_config_manager)

        # Step 2: Environment Manager
        await self._init_step("environment_manager", self._init_environment)

        # Step 3: Registry
        await self._init_step("registry", self._init_registry)

        # Step 4: Dynamic Configuration
        await self._init_step("dynamic_manager", self._init_dynamic)

        # Step 5: Watcher
        if self._enable_watcher:
            await self._init_step("watcher", self._init_watcher)

        # Step 6: Scheduler
        if self._enable_scheduler:
            await self._init_step("scheduler", self._init_scheduler)

        # Step 7: Start lifecycle
        result = await self._lifecycle.startup()

        return {
            "success": result["success"],
            "components": dict(self._components),
            "startup_log": self._startup_log,
            "lifecycle": result,
        }

    async def shutdown(
        self,
        timeout: float = 30.0,
    ) -> Dict[str, Any]:
        """
        Shut down the configuration platform.

        Args:
            timeout: Shutdown timeout.

        Returns:
            Shutdown result.
        """
        result = await self._lifecycle.shutdown(timeout=timeout)

        # Clean up components
        self._components.clear()

        return result

    async def _init_step(
        self,
        name: str,
        init_func: Any,
    ) -> None:
        """Execute a single initialization step."""
        start = datetime.utcnow()
        try:
            result = init_func()
            if asyncio.iscoroutine(result):
                result = await result

            self._components[name] = result
            elapsed = (datetime.utcnow() - start).total_seconds()
            self._startup_log.append({
                "step": name,
                "status": "ok",
                "elapsed": elapsed,
            })
        except Exception as e:
            elapsed = (datetime.utcnow() - start).total_seconds()
            self._startup_log.append({
                "step": name,
                "status": "error",
                "error": str(e),
                "elapsed": elapsed,
            })

    def _init_config_manager(
        self,
    ) -> Any:
        """Initialize configuration manager."""
        from .manager import ConfigurationManager

        manager = self._container.resolve(ConfigurationManager)
        if manager is None:
            manager = ConfigurationManager()
            self._container.register_instance(ConfigurationManager, manager)

        # Load config files if provided
        for filepath in self._config_files:
            try:
                manager.load_from_file(filepath)
            except Exception:
                pass

        return manager

    def _init_environment(
        self,
    ) -> Any:
        """Initialize environment manager."""
        from .environment.manager import EnvironmentManager

        env_manager = self._container.resolve(EnvironmentManager)
        if env_manager is None:
            env_manager = EnvironmentManager()
            self._container.register_instance(EnvironmentManager, env_manager)

        env_manager.init_standard_profiles()
        env_manager.auto_detect()

        return env_manager

    def _init_registry(
        self,
    ) -> Any:
        """Initialize registry."""
        from .registry import ConfigurationRegistry

        registry = self._container.resolve(ConfigurationRegistry)
        if registry is None:
            registry = ConfigurationRegistry()
            self._container.register_instance(ConfigurationRegistry, registry)

        return registry

    def _init_dynamic(
        self,
    ) -> Any:
        """Initialize dynamic configuration manager."""
        from .dynamic.manager import DynamicConfigurationManager

        dynamic_mgr = self._container.resolve(DynamicConfigurationManager)
        if dynamic_mgr is None:
            dynamic_mgr = DynamicConfigurationManager()
            self._container.register_instance(DynamicConfigurationManager, dynamic_mgr)

        return dynamic_mgr

    def _init_watcher(
        self,
    ) -> Any:
        """Initialize file watcher."""
        from .dynamic.watcher import ConfigurationWatcher

        watcher = ConfigurationWatcher()
        for path in self._watch_files:
            watcher.add_file(path)

        return watcher

    def _init_scheduler(
        self,
    ) -> Any:
        """Initialize reload scheduler."""
        from .dynamic.scheduler import ReloadScheduler

        scheduler = ReloadScheduler(reload_func=lambda: None, interval=30.0)
        return scheduler

    def get_status(
        self,
    ) -> Dict[str, Any]:
        """Get bootstrap status."""
        return {
            "lifecycle": self._lifecycle.get_status(),
            "components": list(self._components.keys()),
            "startup_steps": len(self._startup_log),
            "config_files": self._config_files,
            "watch_files": self._watch_files,
        }
