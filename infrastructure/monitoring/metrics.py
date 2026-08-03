"""
Monitoring metrics.

Tracks internal metrics for the
monitoring infrastructure itself,
including collection counts, export
success/failure, and health check
statistics.
"""

from __future__ import annotations

from typing import Any, Dict


class MonitoringMetrics:
    """
    Internal monitoring metrics.

    Tracks operational statistics for
    the monitoring layer, enabling
    self-observation and troubleshooting.

    Usage:
        metrics = MonitoringMetrics()
        metrics.record_collection(150)
        metrics.record_export(True)
        snap = metrics.snapshot()
    """

    def __init__(
        self,
    ) -> None:
        """Initialize monitoring metrics."""

        self._total_collectors: int = 0
        self._collected_points: int = 0
        self._export_count: int = 0
        self._export_failed: int = 0
        self._health_checks: int = 0
        self._collection_errors: int = 0

    def record_collection(
        self,
        num_points: int,
        num_collectors: int = 0,
    ) -> None:
        """
        Record a successful collection.

        Args:
            num_points: Number of points collected.
            num_collectors: Number of collectors used.
        """

        self._collected_points += num_points
        if num_collectors:
            self._total_collectors = max(
                self._total_collectors,
                num_collectors,
            )

    def record_export(
        self,
        success: bool = True,
    ) -> None:
        """
        Record an export attempt.

        Args:
            success: Whether export succeeded.
        """

        self._export_count += 1
        if not success:
            self._export_failed += 1

    def record_health_check(
        self,
    ) -> None:
        """Record a health check execution."""

        self._health_checks += 1

    def record_collection_error(
        self,
    ) -> None:
        """Record a collection error."""

        self._collection_errors += 1

    def snapshot(
        self,
    ) -> Dict[str, Any]:
        """
        Get current metrics snapshot.

        Returns:
            Dictionary with current metric values.
        """

        return {
            "total_collectors": self._total_collectors,
            "collected_points": self._collected_points,
            "export_count": self._export_count,
            "export_failed": self._export_failed,
            "health_checks": self._health_checks,
            "collection_errors": self._collection_errors,
        }

    def reset(
        self,
    ) -> None:
        """Reset all metrics to zero."""

        self._total_collectors = 0
        self._collected_points = 0
        self._export_count = 0
        self._export_failed = 0
        self._health_checks = 0
        self._collection_errors = 0

    def export_prometheus(
        self,
    ) -> Dict[str, float]:
        """
        Export metrics in Prometheus format.

        Returns:
            Dict of metric name → value.
        """

        return {
            "icyquant_monitoring_collectors_total": float(
                self._total_collectors
            ),
            "icyquant_monitoring_points_collected_total": float(
                self._collected_points
            ),
            "icyquant_monitoring_exports_total": float(
                self._export_count
            ),
            "icyquant_monitoring_exports_failed_total": float(
                self._export_failed
            ),
            "icyquant_monitoring_health_checks_total": float(
                self._health_checks
            ),
            "icyquant_monitoring_collection_errors_total": float(
                self._collection_errors
            ),
        }
