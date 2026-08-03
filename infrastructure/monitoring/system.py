"""
System metrics collector.

Collects system-level metrics including
CPU, memory, disk, and network usage
using psutil.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .collector import BaseCollector
from .models import MetricPoint

try:
    import psutil

    PSUTIL_AVAILABLE = True
except ImportError:
    psutil = None  # type: ignore
    PSUTIL_AVAILABLE = False


class SystemCollector(BaseCollector):
    """
    System metrics collector.

    Collects system-level resource metrics
    including CPU, memory, disk, and network
    statistics.

    Metrics:
    - icyquant_cpu_usage_percent: CPU usage
    - icyquant_memory_usage_percent: Memory usage
    - icyquant_memory_available_bytes: Available memory
    - icyquant_disk_usage_percent: Disk usage
    - icyquant_disk_free_bytes: Free disk space
    - icyquant_network_sent_bytes: Network sent
    - icyquant_network_received_bytes: Network received
    - icyquant_network_connections: Active connections
    - icyquant_processes_total: Running processes
    """

    def __init__(
        self,
        namespace: str = "icyquant",
        labels: Optional[Dict[str, str]] = None,
        disk_path: str = "/",
    ) -> None:
        """
        Initialize system collector.

        Args:
            namespace: Metric namespace prefix.
            labels: Default labels.
            disk_path: Path to monitor disk usage for.
        """

        super().__init__(
            name="system",
            namespace=namespace,
            labels=labels,
        )
        self._disk_path = disk_path
        self._psutil_available = PSUTIL_AVAILABLE

    @property
    def is_available(
        self,
    ) -> bool:
        """Check if psutil is available."""
        return self._psutil_available

    async def collect(
        self,
    ) -> List[MetricPoint]:
        """
        Collect system metrics.

        Returns:
            List of MetricPoint objects.
        """

        points: List[MetricPoint] = []

        if not self._psutil_available:
            return points

        # CPU
        try:
            cpu_percent = psutil.cpu_percent(
                interval=None
            )
            points.append(
                self._make_point(
                    "cpu_usage_percent",
                    float(cpu_percent),
                    metric_type="gauge",
                    unit="percent",
                )
            )

            cpu_count = psutil.cpu_count() or 0
            points.append(
                self._make_point(
                    "cpu_cores_total",
                    float(cpu_count),
                    metric_type="gauge",
                    unit="",
                )
            )
        except Exception:
            pass

        # Memory
        try:
            mem = psutil.virtual_memory()
            points.append(
                self._make_point(
                    "memory_usage_percent",
                    float(mem.percent),
                    metric_type="gauge",
                    unit="percent",
                )
            )
            points.append(
                self._make_point(
                    "memory_available_bytes",
                    float(mem.available),
                    metric_type="gauge",
                    unit="bytes",
                )
            )
            points.append(
                self._make_point(
                    "memory_total_bytes",
                    float(mem.total),
                    metric_type="gauge",
                    unit="bytes",
                )
            )
        except Exception:
            pass

        # Disk
        try:
            disk = psutil.disk_usage(
                self._disk_path
            )
            points.append(
                self._make_point(
                    "disk_usage_percent",
                    float(disk.percent),
                    metric_type="gauge",
                    unit="percent",
                )
            )
            points.append(
                self._make_point(
                    "disk_free_bytes",
                    float(disk.free),
                    metric_type="gauge",
                    unit="bytes",
                )
            )
            points.append(
                self._make_point(
                    "disk_total_bytes",
                    float(disk.total),
                    metric_type="gauge",
                    unit="bytes",
                )
            )
        except Exception:
            pass

        # Network
        try:
            net = psutil.net_io_counters()
            points.append(
                self._make_point(
                    "network_sent_bytes",
                    float(net.bytes_sent),
                    metric_type="counter",
                    unit="bytes",
                )
            )
            points.append(
                self._make_point(
                    "network_received_bytes",
                    float(net.bytes_recv),
                    metric_type="counter",
                    unit="bytes",
                )
            )
            points.append(
                self._make_point(
                    "network_packets_sent_total",
                    float(net.packets_sent),
                    metric_type="counter",
                    unit="",
                )
            )
            points.append(
                self._make_point(
                    "network_packets_received_total",
                    float(net.packets_recv),
                    metric_type="counter",
                    unit="",
                )
            )
        except Exception:
            pass

        # Network connections
        try:
            connections = len(
                psutil.net_connections(
                    kind="inet"
                )
            )
            points.append(
                self._make_point(
                    "network_connections",
                    float(connections),
                    metric_type="gauge",
                    unit="",
                )
            )
        except (OSError, PermissionError):
            pass

        # Process count
        try:
            proc_count = len(psutil.pids())
            points.append(
                self._make_point(
                    "processes_total",
                    float(proc_count),
                    metric_type="gauge",
                    unit="",
                )
            )
        except Exception:
            pass

        return points
