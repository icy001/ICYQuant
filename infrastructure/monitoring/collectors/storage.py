"""
Storage metrics collector.

Collects metrics from a StorageMetrics
instance including uploads, downloads,
cache hits/misses, and performance
statistics.

Usage:
    from infrastructure.monitoring.collectors import StorageCollector
    collector = StorageCollector(storage_metrics)
    registry.add_collector("storage", collector)
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..collector import BaseCollector
from ..models import MetricPoint


class StorageCollector(BaseCollector):
    """
    Storage metrics collector.

    Collects storage operation metrics
    including upload/download counts,
    cache hit rates, and latency from
    a StorageMetrics instance.

    Metrics:
    - icyquant_storage_upload_total: Upload count
    - icyquant_storage_download_total: Download count
    - icyquant_storage_delete_total: Delete count
    - icyquant_storage_copy_total: Copy count
    - icyquant_storage_move_total: Move count
    - icyquant_storage_failed_total: Failed operations
    - icyquant_storage_bytes_uploaded: Bytes uploaded
    - icyquant_storage_bytes_downloaded: Bytes downloaded
    - icyquant_storage_cache_hit_total: Cache hits
    - icyquant_storage_cache_miss_total: Cache misses
    - icyquant_storage_cache_hit_ratio: Hit ratio
    - icyquant_storage_latency_ms: Average latency
    - icyquant_storage_total_operations: Total ops
    """

    def __init__(
        self,
        metrics: Optional[Any] = None,
        labels: Optional[Dict[str, str]] = None,
    ) -> None:
        """
        Initialize storage collector.

        Args:
            metrics: StorageMetrics instance.
            labels: Additional labels for all metrics.
        """

        super().__init__(
            name="storage",
            namespace="icyquant",
            labels=labels,
        )
        self._metrics = metrics

    @property
    def is_available(
        self,
    ) -> bool:
        """Check if storage metrics are available."""
        return self._metrics is not None

    async def collect(
        self,
    ) -> List[MetricPoint]:
        """
        Collect storage metrics.

        Returns:
            List of MetricPoint objects.
        """

        points: List[MetricPoint] = []

        if self._metrics is None:
            return points

        try:
            snapshot = self._metrics.snapshot()
        except Exception:
            return points

        # Operation counters
        points.append(
            self._make_point(
                "storage_upload_total",
                float(
                    snapshot.get("upload_count", 0)
                ),
                metric_type="counter",
                unit="",
            )
        )
        points.append(
            self._make_point(
                "storage_download_total",
                float(
                    snapshot.get("download_count", 0)
                ),
                metric_type="counter",
                unit="",
            )
        )
        points.append(
            self._make_point(
                "storage_delete_total",
                float(
                    snapshot.get("delete_count", 0)
                ),
                metric_type="counter",
                unit="",
            )
        )
        points.append(
            self._make_point(
                "storage_copy_total",
                float(
                    snapshot.get("copy_count", 0)
                ),
                metric_type="counter",
                unit="",
            )
        )
        points.append(
            self._make_point(
                "storage_move_total",
                float(
                    snapshot.get("move_count", 0)
                ),
                metric_type="counter",
                unit="",
            )
        )
        points.append(
            self._make_point(
                "storage_failed_total",
                float(
                    snapshot.get("failed_count", 0)
                ),
                metric_type="counter",
                unit="",
            )
        )

        # Byte counts
        points.append(
            self._make_point(
                "storage_bytes_uploaded",
                float(
                    snapshot.get(
                        "bytes_uploaded", 0
                    )
                ),
                metric_type="counter",
                unit="bytes",
            )
        )
        points.append(
            self._make_point(
                "storage_bytes_downloaded",
                float(
                    snapshot.get(
                        "bytes_downloaded", 0
                    )
                ),
                metric_type="counter",
                unit="bytes",
            )
        )

        # Cache metrics
        points.append(
            self._make_point(
                "storage_cache_hit_total",
                float(
                    snapshot.get("cache_hit", 0)
                ),
                metric_type="counter",
                unit="",
            )
        )
        points.append(
            self._make_point(
                "storage_cache_miss_total",
                float(
                    snapshot.get("cache_miss", 0)
                ),
                metric_type="counter",
                unit="",
            )
        )
        points.append(
            self._make_point(
                "storage_cache_hit_ratio",
                float(
                    snapshot.get(
                        "cache_hit_ratio", 0.0
                    )
                ),
                metric_type="gauge",
                unit="",
            )
        )

        # Performance
        points.append(
            self._make_point(
                "storage_latency_ms",
                float(
                    snapshot.get(
                        "average_latency_ms", 0.0
                    )
                ),
                metric_type="gauge",
                unit="ms",
            )
        )
        points.append(
            self._make_point(
                "storage_total_operations",
                float(
                    snapshot.get(
                        "total_operations", 0
                    )
                ),
                metric_type="counter",
                unit="",
            )
        )

        return points