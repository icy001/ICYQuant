"""
Monitoring lifecycle management.

Manages the startup and shutdown
sequence of all monitoring components,
ensuring orderly initialization and
cleanup of collectors, exporters,
alert engine, and scheduler.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

from .alerts import AlertEngine
from .dashboards import DashboardProvisioner, GrafanaDashboard
from .scheduler import MonitoringScheduler
from .service import MonitoringService


class MonitoringLifecycle:
    """
    Monitoring lifecycle manager.

    Coordinates the startup and shutdown
    of all monitoring components in the
    correct order:

    Startup:
    1. MetricsRegistry (already initialized)
    2. AlertEngine
    3. MonitoringService
    4. MonitoringScheduler
    5. DashboardProvisioner (generate configs)

    Shutdown:
    1. MonitoringScheduler (stop background loop)
    2. MonitoringService (flush remaining data)
    3. AlertEngine (resolve pending alerts)
    4. Cleanup

    Usage:
        lifecycle = MonitoringLifecycle(
            service=service,
            scheduler=scheduler,
            alert_engine=alert_engine,
        )
        await lifecycle.startup()
        # ... application runs ...
        await lifecycle.shutdown()
    """

    def __init__(
        self,
        service: MonitoringService,
        scheduler: MonitoringScheduler,
        alert_engine: Optional[AlertEngine] = None,
        provisioner: Optional[DashboardProvisioner] = None,
    ) -> None:
        """
        Initialize lifecycle manager.

        Args:
            service: MonitoringService instance.
            scheduler: MonitoringScheduler instance.
            alert_engine: Optional AlertEngine.
            provisioner: Optional DashboardProvisioner.
        """

        self._service = service
        self._scheduler = scheduler
        self._alert_engine = alert_engine
        self._provisioner = provisioner

        self._started: bool = False
        self._startup_hooks: List[Any] = []
        self._shutdown_hooks: List[Any] = []

    @property
    def is_started(
        self,
    ) -> bool:
        """Check if lifecycle is started."""
        return self._started

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

    async def startup(
        self,
    ) -> None:
        """
        Start all monitoring components.

        Order:
        1. Run startup hooks
        2. Mark service as started
        3. Start scheduler (background collection)
        4. Generate dashboard configs (if provisioner)
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

        # Mark service as started
        self._service._started = True

        # Start scheduler
        await self._scheduler.start()

        # Generate dashboards if provisioner exists
        if self._provisioner is not None:
            try:
                self._provisioner.provision_all()
            except Exception:
                pass

        self._started = True

    async def shutdown(
        self,
    ) -> None:
        """
        Stop all monitoring components.

        Order:
        1. Stop scheduler (stop background loop)
        2. Flush service state
        3. Run shutdown hooks
        4. Clear alert engine state
        """

        if not self._started:
            return

        # Stop scheduler
        await self._scheduler.stop()

        # Mark service as stopped
        self._service._started = False

        # Run shutdown hooks
        for hook in self._shutdown_hooks:
            try:
                result = hook()
                if hasattr(result, "__await__"):
                    await result
            except Exception:
                pass

        # Clear alert engine state
        if self._alert_engine is not None:
            try:
                self._alert_engine.reset()
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
            "service": self._service.get_status(),
            "scheduler": self._scheduler.get_status(),
            "alert_engine": (
                self._alert_engine.get_status()
                if self._alert_engine
                else None
            ),
            "startup_hooks": len(self._startup_hooks),
            "shutdown_hooks": len(self._shutdown_hooks),
        }
