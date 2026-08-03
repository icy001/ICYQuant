"""
Metrics registry.

Central registry for all monitoring
collectors and exporters, managing
registration, lifecycle, and coordinated
data collection across infrastructure
components.

Integrates with PrometheusRegistry for
unified metric creation and exposure.
"""

from __future__ import annotations

import asyncio
import time
from typing import (
    Any,
    Dict,
    List,
    Optional,
)

from .config import MonitoringConfig
from .exceptions import (
    CollectorError,
    ExporterError,
    RegistryError,
)
from .models import (
    HealthSnapshot,
    MetricPoint,
    MetricSnapshot,
)
from .prometheus import PrometheusRegistry


class MetricsRegistry:
    """
    Central metrics registry.

    Manages registration and coordination
    of all metrics collectors and exporters,
    providing a unified interface for the
    monitoring infrastructure.

    Integrates PrometheusRegistry for
    creation of Counter, Gauge, and
    Histogram metrics.

    Responsibilities:
    - Register collectors from infrastructure modules
    - Register exporters for metrics output
    - Coordinate collection cycles
    - Aggregate metrics into snapshots
    - Manage health aggregation
    - Provide Prometheus metric creation

    Usage:
        prom = PrometheusRegistry()
        registry = MetricsRegistry(config, prom)

        db_counter = registry.counter(
            "db_connections", "Active DB connections"
        )
        db_counter.inc()
    """

    def __init__(
        self,
        config: Optional[MonitoringConfig] = None,
        prometheus: Optional[PrometheusRegistry] = None,
    ) -> None:
        """
        Initialize metrics registry.

        Args:
            config: Monitoring configuration.
            prometheus: PrometheusRegistry instance.
        """

        self._config = config or MonitoringConfig()
        self._prometheus = prometheus or PrometheusRegistry()
        self._collectors: Dict[str, Any] = {}
        self._exporters: Dict[str, Any] = {}
        self._health_checkers: Dict[str, Any] = {}
        self._last_collection: Optional[float] = None
        self._last_export: Optional[float] = None

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
    def collectors(
        self,
    ) -> Dict[str, Any]:
        """Get registered collectors."""
        return self._collectors

    @property
    def exporters(
        self,
    ) -> Dict[str, Any]:
        """Get registered exporters."""
        return self._exporters

    @property
    def collector_count(
        self,
    ) -> int:
        """Get number of registered collectors."""
        return len(self._collectors)

    @property
    def exporter_count(
        self,
    ) -> int:
        """Get number of registered exporters."""
        return len(self._exporters)

    # === Prometheus Metric Factory ===

    def counter(
        self,
        name: str,
        description: str,
        labels: Optional[List[str]] = None,
    ) -> Any:
        """
        Create or get a Prometheus Counter.

        Args:
            name: Metric name (will be prefixed with icyquant_).
            description: Help text.
            labels: Label names.

        Returns:
            Counter metric instance.
        """

        return self._prometheus.counter(
            name, description, labels
        )

    def gauge(
        self,
        name: str,
        description: str,
        labels: Optional[List[str]] = None,
    ) -> Any:
        """
        Create or get a Prometheus Gauge.

        Args:
            name: Metric name.
            description: Help text.
            labels: Label names.

        Returns:
            Gauge metric instance.
        """

        return self._prometheus.gauge(
            name, description, labels
        )

    def histogram(
        self,
        name: str,
        description: str,
        labels: Optional[List[str]] = None,
        buckets: Optional[List[float]] = None,
    ) -> Any:
        """
        Create or get a Prometheus Histogram.

        Args:
            name: Metric name.
            description: Help text.
            labels: Label names.
            buckets: Custom bucket boundaries.

        Returns:
            Histogram metric instance.
        """

        return self._prometheus.histogram(
            name, description, labels, buckets
        )

    @property
    def prometheus_registry(
        self,
    ) -> Optional[Any]:
        """Get the underlying Prometheus CollectorRegistry."""
        return self._prometheus.registry

    def generate_prometheus(
        self,
    ) -> str:
        """
        Generate Prometheus text exposition format.

        Returns:
            Prometheus text format string.
        """

        return self._prometheus.generate_metrics()

    # === Collector Management ===

    def add_collector(
        self,
        name: str,
        collector: Any,
    ) -> None:
        """
        Register a metrics collector.

        Args:
            name: Unique collector name.
            collector: Collector instance.

        Raises:
            RegistryError: If collector already registered.
        """

        if name in self._collectors:
            raise RegistryError(
                f"Collector already registered: {name}"
            )

        self._collectors[name] = collector

    def remove_collector(
        self,
        name: str,
    ) -> None:
        """
        Remove a metrics collector.

        Args:
            name: Collector name to remove.
        """

        self._collectors.pop(name, None)

    def add_exporter(
        self,
        name: str,
        exporter: Any,
    ) -> None:
        """
        Register a metrics exporter.

        Args:
            name: Unique exporter name.
            exporter: Exporter instance.

        Raises:
            RegistryError: If exporter already registered.
        """

        if name in self._exporters:
            raise RegistryError(
                f"Exporter already registered: {name}"
            )

        self._exporters[name] = exporter

    def remove_exporter(
        self,
        name: str,
    ) -> None:
        """
        Remove a metrics exporter.

        Args:
            name: Exporter name to remove.
        """

        self._exporters.pop(name, None)

    def add_health_checker(
        self,
        name: str,
        checker: Any,
    ) -> None:
        """
        Register a health checker.

        Args:
            name: Unique checker name.
            checker: Health checker instance.
        """

        self._health_checkers[name] = checker

    def remove_health_checker(
        self,
        name: str,
    ) -> None:
        """
        Remove a health checker.

        Args:
            name: Checker name to remove.
        """

        self._health_checkers.pop(name, None)

    # === Infrastructure Collector Registration ===

    def register_database(
        self,
        database: Any,
        labels: Optional[Dict[str, str]] = None,
    ) -> Any:
        """
        Register database metrics collector.

        Args:
            database: DatabaseEngine instance.
            labels: Additional labels.

        Returns:
            Registered DatabaseCollector.
        """

        from .collectors import DatabaseCollector

        collector = DatabaseCollector(
            database=database,
            labels=labels,
        )
        self.add_collector("database", collector)
        return collector

    def register_redis(
        self,
        metrics: Any,
        labels: Optional[Dict[str, str]] = None,
    ) -> Any:
        """
        Register Redis metrics collector.

        Args:
            metrics: RedisMetrics instance.
            labels: Additional labels.

        Returns:
            Registered RedisCollector.
        """

        from .collectors import RedisCollector

        collector = RedisCollector(
            metrics=metrics,
            labels=labels,
        )
        self.add_collector("redis", collector)
        return collector

    def register_kafka(
        self,
        producer_metrics: Optional[Any] = None,
        consumer_metrics: Optional[Any] = None,
        labels: Optional[Dict[str, str]] = None,
    ) -> Any:
        """
        Register Kafka metrics collector.

        Args:
            producer_metrics: ProducerMetrics instance.
            consumer_metrics: ConsumerMetrics instance.
            labels: Additional labels.

        Returns:
            Registered KafkaCollector.
        """

        from .collectors import KafkaCollector

        collector = KafkaCollector(
            producer_metrics=producer_metrics,
            consumer_metrics=consumer_metrics,
            labels=labels,
        )
        self.add_collector("kafka", collector)
        return collector

    def register_storage(
        self,
        metrics: Any,
        labels: Optional[Dict[str, str]] = None,
    ) -> Any:
        """
        Register storage metrics collector.

        Args:
            metrics: StorageMetrics instance.
            labels: Additional labels.

        Returns:
            Registered StorageCollector.
        """

        from .collectors import StorageCollector

        collector = StorageCollector(
            metrics=metrics,
            labels=labels,
        )
        self.add_collector("storage", collector)
        return collector

    def register_application(
        self,
        labels: Optional[Dict[str, str]] = None,
    ) -> Any:
        """
        Register application metrics collector.

        Args:
            labels: Additional labels.

        Returns:
            Registered ApplicationCollector.
        """

        from .collectors import ApplicationCollector

        collector = ApplicationCollector(
            labels=labels,
        )
        self.add_collector("application", collector)
        return collector

    def register_business(
        self,
        labels: Optional[Dict[str, str]] = None,
    ) -> Any:
        """
        Register business metrics collector.

        Args:
            labels: Additional labels.

        Returns:
            Registered BusinessCollector.
        """

        from .collectors import BusinessCollector

        collector = BusinessCollector(
            labels=labels,
        )
        self.add_collector("business", collector)
        return collector

    # === Collection & Export ===

    async def collect_all(
        self,
    ) -> MetricSnapshot:
        """
        Collect metrics from all registered collectors.

        Returns:
            MetricSnapshot with all collected points.
        """

        if not self._config.enabled:
            return MetricSnapshot(
                namespace=self._config.namespace,
                collectors=len(self._collectors),
            )

        all_points: List[MetricPoint] = []

        for name, collector in self._collectors.items():
            try:
                points = await self._collect_from(
                    name, collector
                )
                all_points.extend(points)
            except Exception:
                pass

        self._last_collection = time.time()

        return MetricSnapshot(
            namespace=self._config.namespace,
            collectors=len(self._collectors),
            points=all_points,
        )

    async def _collect_from(
        self,
        name: str,
        collector: Any,
    ) -> List[MetricPoint]:
        """
        Collect from a single collector.

        Args:
            name: Collector name.
            collector: Collector instance.

        Returns:
            List of metric points.
        """

        try:
            if hasattr(collector, "collect"):
                result = collector.collect()
                if asyncio.iscoroutine(result):
                    result = await result

                if isinstance(result, list):
                    return result
        except Exception:
            pass

        return []

    async def export_snapshot(
        self,
        snapshot: MetricSnapshot,
    ) -> Dict[str, bool]:
        """
        Export snapshot to all registered exporters.

        Args:
            snapshot: Metric snapshot to export.

        Returns:
            Dict mapping exporter name to success status.
        """

        results: Dict[str, bool] = {}

        for name, exporter in self._exporters.items():
            try:
                if hasattr(exporter, "export"):
                    result = exporter.export(snapshot)
                    if asyncio.iscoroutine(result):
                        result = await result
                results[name] = True
            except Exception:
                results[name] = False

        self._last_export = time.time()
        return results

    async def collect_and_export(
        self,
    ) -> MetricSnapshot:
        """
        Collect metrics and immediately export.

        Convenience method for the main loop.

        Returns:
            Collected metric snapshot.
        """

        snapshot = await self.collect_all()
        await self.export_snapshot(snapshot)
        return snapshot

    async def health_check(
        self,
    ) -> HealthSnapshot:
        """
        Perform aggregated health check.

        Returns:
            Aggregated health snapshot.
        """

        components: Dict[str, Any] = {}
        all_healthy = True

        for name, checker in self._health_checkers.items():
            try:
                if hasattr(checker, "check"):
                    result = checker.check()
                    if asyncio.iscoroutine(result):
                        result = await result
                else:
                    result = {"healthy": True}
            except Exception as exc:
                result = {"healthy": False, "error": str(exc)}

            if isinstance(result, tuple):
                healthy, message = result
                result = {
                    "healthy": healthy,
                    "message": message,
                }

            components[name] = result
            if not result.get("healthy", False):
                all_healthy = False

        return HealthSnapshot(
            healthy=all_healthy,
            components=components,
        )

    # === Status ===

    @property
    def last_collection_time(
        self,
    ) -> Optional[float]:
        """Get last collection timestamp."""
        return self._last_collection

    @property
    def last_export_time(
        self,
    ) -> Optional[float]:
        """Get last export timestamp."""
        return self._last_export

    def get_collector_names(
        self,
    ) -> List[str]:
        """Get list of collector names."""
        return list(self._collectors.keys())

    def get_exporter_names(
        self,
    ) -> List[str]:
        """Get list of exporter names."""
        return list(self._exporters.keys())

    def get_health_checker_names(
        self,
    ) -> List[str]:
        """Get list of health checker names."""
        return list(self._health_checkers.keys())

    def get_status(
        self,
    ) -> Dict[str, Any]:
        """
        Get registry status.

        Returns:
            Status dictionary.
        """

        return {
            "collectors": self.collector_count,
            "exporters": self.exporter_count,
            "health_checkers": len(self._health_checkers),
            "prometheus": self._prometheus.get_status(),
            "last_collection": self._last_collection,
            "last_export": self._last_export,
        }
