"""
Metrics exporter interface and implementations.

Defines the protocol for all metrics
exporters and provides PrometheusExporter
for native Prometheus metric exposure.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Protocol

from .models import MetricPoint, MetricSnapshot

try:
    from prometheus_client import generate_latest

    PROMETHEUS_AVAILABLE = True
except ImportError:
    generate_latest = None  # type: ignore
    PROMETHEUS_AVAILABLE = False


class MetricsExporter(Protocol):
    """
    Metrics exporter protocol.

    All metric export backends must
    implement this protocol, allowing
    the monitoring registry to push
    metrics uniformly.

    Implementations should:
    - Accept a MetricSnapshot or list of MetricPoint
    - Push to the target backend
    - Handle errors gracefully

    Usage:
        class PrometheusExporter:
            async def export(self, snapshot):
                text = self._render_text(snapshot)
                await self._push(text)
    """

    async def export(
        self,
        metrics: MetricSnapshot,
    ) -> None:
        """
        Export metrics to the backend.

        Args:
            metrics: MetricSnapshot or list
                     of MetricPoint to export.
        """

        ...


class BaseExporter:
    """
    Base exporter implementation.

    Provides common functionality for
    all exporters, including formatting
    and error handling.

    Subclasses must implement _export().
    """

    def __init__(
        self,
        name: str = "base",
    ) -> None:
        """
        Initialize base exporter.

        Args:
            name: Exporter name.
        """

        self._name = name
        self._export_count = 0
        self._last_export: Optional[float] = None
        self._last_error: Optional[str] = None

    @property
    def name(
        self,
    ) -> str:
        """Get exporter name."""
        return self._name

    @property
    def export_count(
        self,
    ) -> int:
        """Get total export count."""
        return self._export_count

    async def export(
        self,
        snapshot: MetricSnapshot,
    ) -> None:
        """
        Export a metric snapshot.

        Args:
            snapshot: Metrics to export.
        """

        import time

        try:
            await self._export(snapshot)
            self._export_count += 1
            self._last_export = time.time()
            self._last_error = None
        except Exception as exc:
            self._last_error = str(exc)
            raise

    async def _export(
        self,
        snapshot: MetricSnapshot,
    ) -> None:
        """
        Internal export method. Must be implemented by subclasses.

        Args:
            snapshot: Metrics to export.

        Raises:
            NotImplementedError: If not implemented.
        """

        raise NotImplementedError(
            "Subclasses must implement _export()"
        )

    def render_prometheus_text(
        self,
        points: List[MetricPoint],
    ) -> str:
        """
        Render metric points in Prometheus text format.

        Args:
            points: Metric points to render.

        Returns:
            Prometheus exposition format text.
        """

        lines = []
        for p in points:
            lines.append(p.to_prometheus())
        return "\n".join(lines) + "\n"

    def get_status(
        self,
    ) -> Dict[str, Any]:
        """
        Get exporter status.

        Returns:
            Status dictionary.
        """

        return {
            "name": self._name,
            "export_count": self._export_count,
            "last_export": self._last_export,
            "last_error": self._last_error,
        }


class PrometheusExporter(BaseExporter):
    """
    Prometheus metrics exporter.

    Exports metrics to the Prometheus
    exposition format via the prometheus_client
    library's CollectorRegistry.

    This is the primary exporter for the
    ICYQuant platform, serving as the
    single metrics backend.

    Usage:
        prom = PrometheusRegistry()
        exporter = PrometheusExporter(prom)

        # Generate Prometheus text
        text = exporter.generate()

        # Or export a snapshot
        await exporter.export(snapshot)
    """

    def __init__(
        self,
        prometheus_registry: Optional[Any] = None,
    ) -> None:
        """
        Initialize Prometheus exporter.

        Args:
            prometheus_registry: PrometheusRegistry instance.
        """

        super().__init__(name="prometheus")
        self._prom = prometheus_registry
        self._available = PROMETHEUS_AVAILABLE

    @property
    def is_available(
        self,
    ) -> bool:
        """Check if prometheus_client is available."""
        return self._available

    async def _export(
        self,
        snapshot: MetricSnapshot,
    ) -> None:
        """
        Export snapshot to Prometheus registry.

        Args:
            snapshot: Metric snapshot to export.
        """

        if self._prom is not None:
            self._prom.generate_metrics()

    def generate(
        self,
    ) -> str:
        """
        Generate Prometheus text format from registry.

        Returns:
            Prometheus exposition format string.
        """

        if self._prom is not None:
            return self._prom.generate_metrics()

        if self._available and generate_latest is not None:
            result = generate_latest()
            if isinstance(result, bytes):
                return result.decode("utf-8")
            return str(result)

        return ""

    def get_metrics(
        self,
    ) -> Dict[str, Any]:
        """
        Get Prometheus registry status.

        Returns:
            Status dictionary.
        """

        if self._prom is not None:
            return self._prom.get_status()
        return {
            "available": self._available,
            "total_metrics": 0,
        }
