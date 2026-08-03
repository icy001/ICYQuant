"""
Monitoring models.

Defines the core data models for the
monitoring infrastructure, including
metric points, labels, and snapshots.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class MetricPoint:
    """
    A single metric data point.

    Represents a timestamped measurement
    with associated labels for dimensioning
    and aggregation in Prometheus/Grafana.

    Attributes:
        name: Metric name (e.g., icyquant_db_connections).
        value: Metric numeric value.
        labels: Dimension labels for aggregation.
        timestamp: Measurement timestamp.
        type: Metric type (counter, gauge, histogram).
        unit: Unit suffix (seconds, bytes, total).
    """

    name: str
    value: float
    labels: Dict[str, str] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    type: str = "gauge"
    unit: str = ""

    def to_prometheus(
        self,
    ) -> str:
        """
        Convert to Prometheus text format.

        Returns:
            Prometheus exposition format line.
        """

        label_str = ",".join(
            f'{k}="{v}"'
            for k, v in sorted(self.labels.items())
        )
        labels_part = (
            f"{{{label_str}}}" if label_str else ""
        )
        ts_ms = int(
            self.timestamp.timestamp() * 1000
        )
        return (
            f"{self.name}{labels_part} "
            f"{self.value} {ts_ms}"
        )


@dataclass
class MetricSnapshot:
    """
    Snapshot of all metrics at a point in time.

    Captures the full state of collected
    metrics for export or analysis.

    Attributes:
        namespace: Metric namespace.
        timestamp: Snapshot timestamp.
        points: List of metric points.
        collectors: Number of collectors.
    """

    namespace: str = "icyquant"
    timestamp: datetime = field(default_factory=datetime.utcnow)
    points: List[MetricPoint] = field(default_factory=list)
    collectors: int = 0

    def to_dict(
        self,
    ) -> Dict[str, Any]:
        """
        Convert snapshot to dictionary.

        Returns:
            Dictionary representation.
        """

        return {
            "namespace": self.namespace,
            "timestamp": self.timestamp.isoformat(),
            "collectors": self.collectors,
            "points": [
                {
                    "name": p.name,
                    "value": p.value,
                    "labels": p.labels,
                    "type": p.type,
                    "unit": p.unit,
                    "timestamp": p.timestamp.isoformat(),
                }
                for p in self.points
            ],
        }


@dataclass
class HealthSnapshot:
    """
    Aggregated health snapshot.

    Combines health status from all
    infrastructure components into
    a single view.

    Attributes:
        healthy: Overall health status.
        components: Per-component health status.
        timestamp: Snapshot timestamp.
    """

    healthy: bool = True
    components: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(
        self,
    ) -> Dict[str, Any]:
        """
        Convert to dictionary.

        Returns:
            Dictionary representation.
        """

        return {
            "healthy": self.healthy,
            "timestamp": self.timestamp.isoformat(),
            "components": self.components,
        }
