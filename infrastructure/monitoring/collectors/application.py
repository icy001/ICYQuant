"""
Application metrics collector.

Collects application-level metrics including
HTTP request counts, API latency, worker
queue depth, and error rates.

This collector tracks its own counters
for application-level events, providing
a unified view of request throughput
and processing performance.

Usage:
    from infrastructure.monitoring.collectors import ApplicationCollector
    collector = ApplicationCollector()
    collector.record_request(path="/api/orders", latency_ms=45.2)
    collector.record_error(path="/api/orders")
    registry.add_collector("application", collector)
"""

from __future__ import annotations

import time
from collections import defaultdict
from typing import Any, Dict, List, Optional

from ..collector import BaseCollector
from ..models import MetricPoint


class ApplicationCollector(BaseCollector):
    """
    Application-level metrics collector.

    Tracks HTTP requests, API latency,
    worker tasks, and error rates for
    application-level observability.

    Metrics:
    - icyquant_http_requests_total: Request count
    - icyquant_http_request_duration_ms: Request latency
    - icyquant_worker_tasks: Active tasks
    - icyquant_application_errors_total: Error count
    - icyquant_application_request_rate: Request rate
    """

    def __init__(
        self,
        labels: Optional[Dict[str, str]] = None,
    ) -> None:
        """
        Initialize application collector.

        Args:
            labels: Additional labels for all metrics.
        """

        super().__init__(
            name="application",
            namespace="icyquant",
            labels=labels,
        )
        self._request_counts: Dict[str, int] = defaultdict(int)
        self._error_counts: Dict[str, int] = defaultdict(int)
        self._total_latency: Dict[str, float] = defaultdict(float)
        self._total_requests: int = 0
        self._total_errors: int = 0
        self._started_at: float = time.time()
        self._active_tasks: int = 0

    @property
    def is_available(
        self,
    ) -> bool:
        """Application collector is always available."""
        return True

    def record_request(
        self,
        path: str = "",
        latency_ms: float = 0.0,
    ) -> None:
        """
        Record an HTTP/API request.

        Args:
            path: Request path or endpoint.
            latency_ms: Request latency in milliseconds.
        """

        self._request_counts[path] += 1
        self._total_latency[path] += latency_ms
        self._total_requests += 1

    def record_error(
        self,
        path: str = "",
    ) -> None:
        """
        Record a request error.

        Args:
            path: Request path or endpoint.
        """

        self._error_counts[path] += 1
        self._total_errors += 1

    def set_active_tasks(
        self,
        count: int,
    ) -> None:
        """
        Set current active worker task count.

        Args:
            count: Number of active tasks.
        """

        self._active_tasks = count

    async def collect(
        self,
    ) -> List[MetricPoint]:
        """
        Collect application metrics.

        Returns:
            List of MetricPoint objects.
        """

        points: List[MetricPoint] = []
        now = time.time()
        uptime = now - self._started_at

        # Request rate
        request_rate = (
            self._total_requests / uptime
            if uptime > 0
            else 0.0
        )
        points.append(
            self._make_point(
                "application_request_rate",
                request_rate,
                metric_type="gauge",
                unit="req/s",
            )
        )

        # Total requests
        points.append(
            self._make_point(
                "http_requests_total",
                float(self._total_requests),
                metric_type="counter",
                unit="",
            )
        )

        # Total errors
        points.append(
            self._make_point(
                "application_errors_total",
                float(self._total_errors),
                metric_type="counter",
                unit="",
            )
        )

        # Error rate
        error_rate = (
            self._total_errors / self._total_requests
            if self._total_requests > 0
            else 0.0
        )
        points.append(
            self._make_point(
                "application_error_rate",
                error_rate,
                metric_type="gauge",
                unit="",
            )
        )

        # Active worker tasks
        points.append(
            self._make_point(
                "worker_tasks",
                float(self._active_tasks),
                metric_type="gauge",
                unit="",
            )
        )

        # Per-path breakdown
        for path, count in self._request_counts.items():
            path_label = path.replace("/", "_") or "root"
            extra = {"endpoint": path}
            points.append(
                self._make_point(
                    "http_requests_total",
                    float(count),
                    metric_type="counter",
                    unit="",
                    extra_labels=extra,
                )
            )

            avg_latency = (
                self._total_latency[path] / count
                if count > 0
                else 0.0
            )
            points.append(
                self._make_point(
                    "http_request_duration_ms",
                    avg_latency,
                    metric_type="gauge",
                    unit="ms",
                    extra_labels=extra,
                )
            )

            err_count = self._error_counts.get(path, 0)
            if err_count > 0:
                points.append(
                    self._make_point(
                        "application_errors_total",
                        float(err_count),
                        metric_type="counter",
                        unit="",
                        extra_labels=extra,
                    )
                )

        return points