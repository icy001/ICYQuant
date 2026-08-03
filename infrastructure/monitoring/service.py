"""
Monitoring service.

Unified entry point for the monitoring
platform, coordinating collection, alert
evaluation, and export in a single
service interface.

Usage:
    service = MonitoringService(
        registry=registry,
        collector=collector,
        exporter=exporter,
    )
    metrics = await service.collect()
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from .collector import CollectorRunner
from .exporter import PrometheusExporter
from .models import MetricPoint, MetricSnapshot
from .registry import MetricsRegistry


class MonitoringService:
    """
    Unified monitoring service.

    Coordinates the full monitoring pipeline:
    1. Collect metrics from all registered collectors
    2. Evaluate alert rules against collected metrics
    3. Export metrics to Prometheus

    Attributes:
        registry: MetricsRegistry instance.
        collector: CollectorRunner instance.
        exporter: PrometheusExporter instance.
        alert_engine: Optional AlertEngine for alert evaluation.
    """

    def __init__(
        self,
        registry: MetricsRegistry,
        collector: CollectorRunner,
        exporter: PrometheusExporter,
        alert_engine: Optional[Any] = None,
    ) -> None:
        """
        Initialize monitoring service.

        Args:
            registry: MetricsRegistry instance.
            collector: CollectorRunner instance.
            exporter: PrometheusExporter instance.
            alert_engine: Optional AlertEngine for alert processing.
        """

        self._registry = registry
        self._collector = collector
        self._exporter = exporter
        self._alert_engine = alert_engine

        self._collect_count: int = 0
        self._last_collect_time: Optional[float] = None
        self._last_metrics: List[MetricPoint] = []
        self._started: bool = False

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
    ) -> Optional[Any]:
        """Get alert engine."""
        return self._alert_engine

    @property
    def collect_count(
        self,
    ) -> int:
        """Get total collect count."""
        return self._collect_count

    @property
    def is_started(
        self,
    ) -> bool:
        """Check if service is started."""
        return self._started

    async def collect(
        self,
    ) -> List[MetricPoint]:
        """
        Execute a single monitoring cycle.

        Collects metrics from all collectors,
        evaluates alert rules if alert engine
        is configured, and exports to Prometheus.

        Returns:
            List of collected MetricPoint objects.
        """

        # Collect from all registered collectors
        metrics = await self._collector.collect_all()
        self._last_metrics = metrics

        # Evaluate alert rules
        if self._alert_engine is not None:
            try:
                await self._alert_engine.process(metrics)
            except Exception:
                pass

        # Export to Prometheus
        try:
            await self._exporter.export(
                MetricSnapshot(
                    namespace=self._registry.config.namespace,
                    points=metrics,
                    collectors=self._registry.collector_count,
                )
            )
        except Exception:
            pass

        self._collect_count += 1
        self._last_collect_time = time.time()

        return metrics

    async def collect_snapshot(
        self,
    ) -> MetricSnapshot:
        """
        Collect and return as MetricSnapshot.

        Returns:
            MetricSnapshot with all collected points.
        """

        points = await self.collect()
        return MetricSnapshot(
            namespace=self._registry.config.namespace,
            points=points,
            collectors=self._registry.collector_count,
        )

    def generate_prometheus(
        self,
    ) -> str:
        """
        Generate Prometheus text exposition format.

        Returns:
            Prometheus text format string.
        """

        return self._registry.generate_prometheus()

    def get_status(
        self,
    ) -> Dict[str, Any]:
        """
        Get service status.

        Returns:
            Status dictionary.
        """

        return {
            "started": self._started,
            "collect_count": self._collect_count,
            "last_collect_time": self._last_collect_time,
            "collectors": self._registry.collector_count,
            "exporters": self._registry.exporter_count,
            "alert_engine": (
                self._alert_engine is not None
            ),
            "last_metric_count": len(self._last_metrics),
        }

    async def health_check(
        self,
    ) -> Dict[str, Any]:
        """
        Check monitoring service health.

        Returns:
            Health status dictionary.
        """

        return {
            "monitoring": True,
            "collector": self._registry.collector_count > 0,
            "exporter": self._exporter is not None,
            "alert_engine": self._alert_engine is not None,
            "started": self._started,
        }
