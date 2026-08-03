"""
Storage metrics collection.

Provides runtime metrics tracking for
storage operations including uploads,
downloads, cache hits/misses, and
performance statistics.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from time import perf_counter


@dataclass
class StorageMetrics:
    """
    Storage operation metrics.

    Tracks counters and statistics for
    all storage operations, providing
    insights into usage patterns and
    performance.

    Attributes:
        upload_count: Total number of uploads.
        download_count: Total number of downloads.
        delete_count: Total number of deletes.
        copy_count: Total number of copies.
        move_count: Total number of moves.
        failed_count: Total number of failed operations.
        bytes_uploaded: Total bytes uploaded.
        bytes_downloaded: Total bytes downloaded.
        cache_hit: Number of cache hits.
        cache_miss: Number of cache misses.
        total_latency_ms: Total latency in milliseconds.
        operation_count: Total operations for latency calc.
    """

    upload_count: int = 0
    download_count: int = 0
    delete_count: int = 0
    copy_count: int = 0
    move_count: int = 0
    failed_count: int = 0

    bytes_uploaded: int = 0
    bytes_downloaded: int = 0

    cache_hit: int = 0
    cache_miss: int = 0

    total_latency_ms: float = 0.0
    operation_count: int = 0

    def record_upload(
        self,
        size: int,
        latency_ms: float,
    ) -> None:
        """
        Record an upload operation.

        Args:
            size: Bytes uploaded.
            latency_ms: Operation latency.
        """

        self.upload_count += 1
        self.bytes_uploaded += size
        self._record_latency(latency_ms)

    def record_download(
        self,
        size: int,
        latency_ms: float,
    ) -> None:
        """
        Record a download operation.

        Args:
            size: Bytes downloaded.
            latency_ms: Operation latency.
        """

        self.download_count += 1
        self.bytes_downloaded += size
        self._record_latency(latency_ms)

    def record_delete(
        self,
        latency_ms: float,
    ) -> None:
        """
        Record a delete operation.

        Args:
            latency_ms: Operation latency.
        """

        self.delete_count += 1
        self._record_latency(latency_ms)

    def record_copy(
        self,
        latency_ms: float,
    ) -> None:
        """
        Record a copy operation.

        Args:
            latency_ms: Operation latency.
        """

        self.copy_count += 1
        self._record_latency(latency_ms)

    def record_move(
        self,
        latency_ms: float,
    ) -> None:
        """
        Record a move operation.

        Args:
            latency_ms: Operation latency.
        """

        self.move_count += 1
        self._record_latency(latency_ms)

    def record_failure(
        self,
    ) -> None:
        """Record a failed operation."""
        self.failed_count += 1

    def record_cache_hit(
        self,
    ) -> None:
        """Record a cache hit."""
        self.cache_hit += 1

    def record_cache_miss(
        self,
    ) -> None:
        """Record a cache miss."""
        self.cache_miss += 1

    def _record_latency(
        self,
        latency_ms: float,
    ) -> None:
        """
        Record operation latency.

        Args:
            latency_ms: Operation latency in ms.
        """

        self.total_latency_ms += latency_ms
        self.operation_count += 1

    @property
    def average_latency_ms(
        self,
    ) -> float:
        """
        Get average operation latency.

        Returns:
            Average latency in milliseconds.
        """

        if self.operation_count == 0:
            return 0.0
        return self.total_latency_ms / self.operation_count

    @property
    def cache_hit_ratio(
        self,
    ) -> float:
        """
        Get cache hit ratio.

        Returns:
            Cache hit ratio (0.0-1.0).
        """

        total = self.cache_hit + self.cache_miss
        if total == 0:
            return 0.0
        return self.cache_hit / total

    @property
    def total_operations(
        self,
    ) -> int:
        """
        Get total operations count.

        Returns:
            Total storage operations performed.
        """

        return (
            self.upload_count
            + self.download_count
            + self.delete_count
            + self.copy_count
            + self.move_count
        )

    def snapshot(
        self,
    ) -> Dict[str, Any]:
        """
        Get current metrics snapshot.

        Returns:
            Dictionary with current metrics.
        """

        return {
            "upload_count": self.upload_count,
            "download_count": self.download_count,
            "delete_count": self.delete_count,
            "copy_count": self.copy_count,
            "move_count": self.move_count,
            "failed_count": self.failed_count,
            "bytes_uploaded": self.bytes_uploaded,
            "bytes_downloaded": self.bytes_downloaded,
            "cache_hit": self.cache_hit,
            "cache_miss": self.cache_miss,
            "cache_hit_ratio": round(
                self.cache_hit_ratio, 4
            ),
            "average_latency_ms": round(
                self.average_latency_ms, 2
            ),
            "total_operations": self.total_operations,
        }

    def reset(
        self,
    ) -> None:
        """Reset all metrics to zero."""
        self.upload_count = 0
        self.download_count = 0
        self.delete_count = 0
        self.copy_count = 0
        self.move_count = 0
        self.failed_count = 0
        self.bytes_uploaded = 0
        self.bytes_downloaded = 0
        self.cache_hit = 0
        self.cache_miss = 0
        self.total_latency_ms = 0.0
        self.operation_count = 0


class StorageMetricsExporter:
    """
    Export storage metrics for monitoring.

    Converts StorageMetrics to Prometheus-compatible
    format for integration with monitoring systems.
    """

    def export(
        self,
        metrics: StorageMetrics,
    ) -> Dict[str, float]:
        """
        Export metrics as flat dictionary.

        Args:
            metrics: Storage metrics instance.

        Returns:
            Dictionary with Prometheus-compatible metric names.
        """

        snapshot = metrics.snapshot()

        return {
            "storage_uploads_total": float(
                snapshot["upload_count"]
            ),
            "storage_downloads_total": float(
                snapshot["download_count"]
            ),
            "storage_deletes_total": float(
                snapshot["delete_count"]
            ),
            "storage_copies_total": float(
                snapshot["copy_count"]
            ),
            "storage_moves_total": float(
                snapshot["move_count"]
            ),
            "storage_failures_total": float(
                snapshot["failed_count"]
            ),
            "storage_bytes_uploaded": float(
                snapshot["bytes_uploaded"]
            ),
            "storage_bytes_downloaded": float(
                snapshot["bytes_downloaded"]
            ),
            "storage_cache_hits_total": float(
                snapshot["cache_hit"]
            ),
            "storage_cache_misses_total": float(
                snapshot["cache_miss"]
            ),
            "storage_cache_hit_ratio": float(
                snapshot["cache_hit_ratio"]
            ),
            "storage_average_latency_ms": float(
                snapshot["average_latency_ms"]
            ),
            "storage_total_operations": float(
                snapshot["total_operations"]
            ),
        }