"""
Metrics collector interface and runner.

Defines the protocol for all metrics
collectors and provides a CollectorRunner
for coordinated execution across multiple
collectors.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional, Protocol

from .models import MetricPoint


class MetricsCollector(Protocol):
    """
    Metrics collector protocol.

    All infrastructure components that
    produce metrics must implement this
    protocol, allowing the monitoring
    registry to collect metrics uniformly.

    Implementations should:
    - Return a list of MetricPoint objects
    - Use the namespace prefix for naming
    - Include default labels for aggregation

    Usage:
        class DatabaseCollector:
            async def collect(self) -> list[MetricPoint]:
                return [
                    MetricPoint(
                        name="icyquant_db_connections",
                        value=pool.size(),
                        labels={"module": "database"},
                    )
                ]
    """

    async def collect(
        self,
    ) -> List[MetricPoint]:
        """
        Collect metrics from the component.

        Returns:
            List of MetricPoint objects
            representing current measurements.
        """

        ...


class BaseCollector:
    """
    Base collector implementation.

    Provides common functionality for
    all collectors, including label
    management and error handling.

    Subclasses must implement collect().
    """

    def __init__(
        self,
        name: str,
        namespace: str = "icyquant",
        labels: Optional[Dict[str, str]] = None,
    ) -> None:
        """
        Initialize base collector.

        Args:
            name: Collector name (e.g., "database").
            namespace: Metric namespace prefix.
            labels: Default labels for all metrics.
        """

        self._name = name
        self._namespace = namespace
        self._labels = labels or {}

    @property
    def name(
        self,
    ) -> str:
        """Get collector name."""
        return self._name

    def _make_name(
        self,
        metric_name: str,
    ) -> str:
        """
        Build fully qualified metric name.

        Args:
            metric_name: Base metric name.

        Returns:
            Fully qualified name with namespace.
        """

        return f"{self._namespace}_{metric_name}"

    def _make_point(
        self,
        name: str,
        value: float,
        metric_type: str = "gauge",
        unit: str = "",
        extra_labels: Optional[Dict[str, str]] = None,
    ) -> MetricPoint:
        """
        Create a properly labeled metric point.

        Args:
            name: Metric name (without namespace).
            value: Metric value.
            metric_type: Metric type.
            unit: Unit suffix.
            extra_labels: Additional labels.

        Returns:
            Configured MetricPoint.
        """

        labels = dict(self._labels)
        if extra_labels:
            labels.update(extra_labels)
        if "module" not in labels:
            labels["module"] = self._name

        return MetricPoint(
            name=self._make_name(name),
            value=value,
            labels=labels,
            type=metric_type,
            unit=unit,
        )

    async def collect(
        self,
    ) -> List[MetricPoint]:
        """
        Collect metrics. Must be implemented by subclasses.

        Returns:
            List of MetricPoint objects.

        Raises:
            NotImplementedError: If not implemented.
        """

        raise NotImplementedError(
            "Subclasses must implement collect()"
        )


class CollectorRunner:
    """
    Collector execution runner.

    Manages coordinated execution of
    multiple collectors, collecting
    metrics concurrently and aggregating
    results.

    Usage:
        runner = CollectorRunner(registry)
        runner.add_collector(sys_collector)
        runner.add_collector(runtime_collector)
        snapshot = await runner.collect_all()
    """

    def __init__(
        self,
        registry: Any,
        continue_on_error: bool = True,
    ) -> None:
        """
        Initialize collector runner.

        Args:
            registry: MetricsRegistry instance.
            continue_on_error: Continue if one collector fails.
        """

        self._registry = registry
        self._continue_on_error = continue_on_error
        self._last_results: Dict[str, List[MetricPoint]] = {}

    async def collect_all(
        self,
    ) -> List[MetricPoint]:
        """
        Run all registered collectors concurrently.

        Returns:
            Aggregated list of all metric points.
        """

        collectors = self._registry.collectors
        all_points: List[MetricPoint] = []
        results: Dict[str, List[MetricPoint]] = {}

        async def _run_collector(
            name: str,
            collector: Any,
        ) -> None:
            try:
                if hasattr(collector, "collect"):
                    result = collector.collect()
                    if asyncio.iscoroutine(result):
                        result = await result

                    if isinstance(result, list):
                        results[name] = result
            except Exception:
                if not self._continue_on_error:
                    raise

        tasks = [
            _run_collector(name, c)
            for name, c in collectors.items()
        ]

        await asyncio.gather(
            *tasks,
            return_exceptions=self._continue_on_error,
        )

        for name, points in results.items():
            all_points.extend(points)

        self._last_results = results
        return all_points

    @property
    def last_results(
        self,
    ) -> Dict[str, List[MetricPoint]]:
        """Get last collection results per collector."""
        return self._last_results

    def get_collector_result(
        self,
        name: str,
    ) -> List[MetricPoint]:
        """
        Get last result for a specific collector.

        Args:
            name: Collector name.

        Returns:
            List of metric points from last run.
        """

        return self._last_results.get(name, [])
