"""
Monitoring bootstrap.

Provides a single entry point for
initializing and managing the entire
monitoring platform, wiring together
all components through dependency
injection.

Usage:
    bootstrap = MonitoringBootstrap(
        config=MonitoringConfig(),
    )

    await bootstrap.startup()

    # Access components
    registry = bootstrap.registry
    service = bootstrap.service

    # Register infrastructure collectors
    registry.register_database(db_engine)
    registry.register_redis(redis_metrics)

    await bootstrap.shutdown()
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from .alerts import AlertEngine, AlertRouter, AlertSuppression, EscalationPolicy
from .collector import CollectorRunner
from .config import MonitoringConfig
from .dashboards import DashboardProvisioner, GrafanaDashboard
from .exporter import PrometheusExporter
from .lifecycle import MonitoringLifecycle
from .prometheus import PrometheusRegistry
from .registry import MetricsRegistry
from .scheduler import MonitoringScheduler
from .service import MonitoringService
from .telemetry import TelemetryService
from .tracing import MonitoringTracing


class MonitoringBootstrap:
    """
    Monitoring platform bootstrap.

    Initializes and wires together all
    monitoring components:

    - PrometheusRegistry → MetricsRegistry
    - CollectorRunner → MonitoringService
    - PrometheusExporter → MonitoringService
    - AlertEngine (optional) → MonitoringService
    - MonitoringService → MonitoringScheduler
    - MonitoringScheduler → MonitoringLifecycle
    - TelemetryService (standalone)
    - MonitoringTracing (standalone)
    - GrafanaDashboard + DashboardProvisioner

    All components are accessible as
    properties after initialization.

    Usage:
        bootstrap = MonitoringBootstrap()

        # Add alert rules before startup
        bootstrap.add_alert_rule(AlertRule(...))

        await bootstrap.startup()

        # Register collectors after startup
        bootstrap.registry.register_database(db)

        await bootstrap.shutdown()
    """

    def __init__(
        self,
        config: Optional[MonitoringConfig] = None,
        registry: Optional[MetricsRegistry] = None,
        collector: Optional[CollectorRunner] = None,
        exporter: Optional[PrometheusExporter] = None,
        alert_engine: Optional[AlertEngine] = None,
        enable_alerts: bool = True,
        enable_dashboards: bool = True,
    ) -> None:
        """
        Initialize monitoring bootstrap.

        Args:
            config: Monitoring configuration.
            registry: Pre-configured MetricsRegistry.
            collector: Pre-configured CollectorRunner.
            exporter: Pre-configured PrometheusExporter.
            alert_engine: Pre-configured AlertEngine.
            enable_alerts: Whether to create alert engine.
            enable_dashboards: Whether to create dashboard provisioner.
        """

        self._config = config or MonitoringConfig()

        # Core components
        self._prometheus = (
            registry.prometheus
            if registry is not None
            else PrometheusRegistry()
        )
        self._registry = registry or MetricsRegistry(
            config=self._config,
            prometheus=self._prometheus,
        )
        self._collector = collector or CollectorRunner(
            self._registry
        )
        self._exporter = exporter or PrometheusExporter(
            self._prometheus
        )

        # Alert engine
        self._alert_engine = alert_engine
        if self._alert_engine is None and enable_alerts:
            suppression = AlertSuppression(
                cooldown_seconds=self._config.collect_interval * 4,
            )
            escalation = EscalationPolicy()
            router = AlertRouter(
                suppression=suppression,
                escalation=escalation,
            )
            self._alert_engine = AlertEngine(router=router)

        # Service
        self._service = MonitoringService(
            registry=self._registry,
            collector=self._collector,
            exporter=self._exporter,
            alert_engine=self._alert_engine,
        )

        # Scheduler
        self._scheduler = MonitoringScheduler(
            service=self._service,
            interval=self._config.collect_interval,
        )

        # Dashboard provisioner
        self._dashboard_generator: Optional[GrafanaDashboard] = None
        self._provisioner: Optional[DashboardProvisioner] = None
        if enable_dashboards:
            self._dashboard_generator = GrafanaDashboard()
            self._provisioner = DashboardProvisioner(
                generator=self._dashboard_generator,
            )

        # Telemetry
        self._telemetry = TelemetryService()

        # Tracing
        self._tracing = MonitoringTracing()

        # Lifecycle
        self._lifecycle = MonitoringLifecycle(
            service=self._service,
            scheduler=self._scheduler,
            alert_engine=self._alert_engine,
            provisioner=self._provisioner,
        )

    # === Properties ===

    @property
    def config(
        self,
    ) -> MonitoringConfig:
        """Get monitoring configuration."""
        return self._config

    @property
    def prometheus(
        self,
    ) -> PrometheusRegistry:
        """Get Prometheus registry."""
        return self._prometheus

    @property
    def registry(
        self,
    ) -> MetricsRegistry:
        """Get metrics registry."""
        return self._registry

    @property
    def collector(
        self,
    ) -> CollectorRunner:
        """Get collector runner."""
        return self._collector

    @property
    def exporter(
        self,
    ) -> PrometheusExporter:
        """Get exporter."""
        return self._exporter

    @property
    def alert_engine(
        self,
    ) -> Optional[AlertEngine]:
        """Get alert engine."""
        return self._alert_engine

    @property
    def service(
        self,
    ) -> MonitoringService:
        """Get monitoring service."""
        return self._service

    @property
    def scheduler(
        self,
    ) -> MonitoringScheduler:
        """Get scheduler."""
        return self._scheduler

    @property
    def telemetry(
        self,
    ) -> TelemetryService:
        """Get telemetry service."""
        return self._telemetry

    @property
    def tracing(
        self,
    ) -> MonitoringTracing:
        """Get tracing service."""
        return self._tracing

    @property
    def lifecycle(
        self,
    ) -> MonitoringLifecycle:
        """Get lifecycle manager."""
        return self._lifecycle

    @property
    def provisioner(
        self,
    ) -> Optional[DashboardProvisioner]:
        """Get dashboard provisioner."""
        return self._provisioner

    @property
    def dashboard_generator(
        self,
    ) -> Optional[GrafanaDashboard]:
        """Get dashboard generator."""
        return self._dashboard_generator

    @property
    def is_started(
        self,
    ) -> bool:
        """Check if monitoring is started."""
        return self._lifecycle.is_started

    # === Convenience Methods ===

    def add_alert_rule(
        self,
        rule: Any,
    ) -> None:
        """
        Add an alert rule to the alert engine.

        Args:
            rule: AlertRule to add.
        """

        if self._alert_engine is not None:
            self._alert_engine.add_rule(rule)

    def add_collector(
        self,
        name: str,
        collector: Any,
    ) -> None:
        """
        Register a metrics collector.

        Args:
            name: Collector name.
            collector: Collector instance.
        """

        self._registry.add_collector(name, collector)

    def add_exporter(
        self,
        name: str,
        exporter: Any,
    ) -> None:
        """
        Register a metrics exporter.

        Args:
            name: Exporter name.
            exporter: Exporter instance.
        """

        self._registry.add_exporter(name, exporter)

    def add_health_checker(
        self,
        name: str,
        checker: Any,
    ) -> None:
        """
        Register a health checker.

        Args:
            name: Checker name.
            checker: Health checker instance.
        """

        self._registry.add_health_checker(name, checker)

    # === Lifecycle ===

    async def startup(
        self,
    ) -> None:
        """
        Start the monitoring platform.

        Initializes all components and
        starts the background scheduler.
        """

        await self._lifecycle.startup()

    async def shutdown(
        self,
    ) -> None:
        """
        Stop the monitoring platform.

        Stops the scheduler and cleans
        up all resources.
        """

        await self._lifecycle.shutdown()

    # === Health ===

    async def health_check(
        self,
    ) -> Dict[str, Any]:
        """
        Perform comprehensive health check.

        Returns:
            Health status dictionary for all
            monitoring components.
        """

        components: Dict[str, Any] = {}

        # Service health
        service_health = await self._service.health_check()
        components["monitoring"] = service_health

        # Scheduler health
        components["scheduler"] = {
            "running": self._scheduler.is_running,
            "cycles": self._scheduler.cycle_count,
            "errors": self._scheduler.error_count,
        }

        # Alert engine health
        if self._alert_engine is not None:
            components["alert_engine"] = {
                "rules": self._alert_engine.rules.count,
                "history": self._alert_engine.history.count,
            }

        # Telemetry health
        components["telemetry"] = self._telemetry.get_status()

        # Tracing health
        components["tracing"] = self._tracing.get_status()

        # Registry health
        components["registry"] = {
            "collectors": self._registry.collector_count,
            "exporters": self._registry.exporter_count,
        }

        # Overall health
        all_healthy = (
            self._lifecycle.is_started
            and self._scheduler.error_count == 0
        )

        return {
            "healthy": all_healthy,
            "started": self._lifecycle.is_started,
            "components": components,
        }

    def get_status(
        self,
    ) -> Dict[str, Any]:
        """
        Get complete monitoring platform status.

        Returns:
            Status dictionary.
        """

        return {
            "started": self._lifecycle.is_started,
            "config": {
                "namespace": self._config.namespace,
                "collect_interval": self._config.collect_interval,
                "enabled": self._config.enabled,
            },
            "registry": self._registry.get_status(),
            "service": self._service.get_status(),
            "scheduler": self._scheduler.get_status(),
            "alert_engine": (
                self._alert_engine.get_status()
                if self._alert_engine
                else None
            ),
            "lifecycle": self._lifecycle.get_status(),
            "telemetry": self._telemetry.get_status(),
            "tracing": self._tracing.get_status(),
        }
