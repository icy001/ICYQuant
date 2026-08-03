"""
Redis metrics collector.

Collects metrics from a RedisMetrics
instance including cache hit/miss rates,
command counts, and latency.

Usage:
    from infrastructure.monitoring.collectors import RedisCollector
    collector = RedisCollector(redis_metrics)
    registry.add_collector("redis", collector)
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..collector import BaseCollector
from ..models import MetricPoint


class RedisCollector(BaseCollector):
    """
    Redis metrics collector.

    Collects cache statistics, command counts,
    message throughput, and latency from a
    RedisMetrics instance.

    Metrics:
    - icyquant_redis_cache_hit_total: Cache hits
    - icyquant_redis_cache_miss_total: Cache misses
    - icyquant_redis_cache_hit_ratio: Hit ratio
    - icyquant_redis_commands_total: Total commands
    - icyquant_redis_failed_total: Failed commands
    - icyquant_redis_published_total: Published messages
    - icyquant_redis_consumed_total: Consumed messages
    - icyquant_redis_latency_ms: Average latency
    """

    def __init__(
        self,
        metrics: Optional[Any] = None,
        labels: Optional[Dict[str, str]] = None,
    ) -> None:
        """
        Initialize Redis collector.

        Args:
            metrics: RedisMetrics instance.
            labels: Additional labels for all metrics.
        """

        super().__init__(
            name="redis",
            namespace="icyquant",
            labels=labels,
        )
        self._metrics = metrics

    @property
    def is_available(
        self,
    ) -> bool:
        """Check if Redis metrics are available."""
        return self._metrics is not None

    async def collect(
        self,
    ) -> List[MetricPoint]:
        """
        Collect Redis metrics.

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

        # Cache metrics
        points.append(
            self._make_point(
                "redis_cache_hit_total",
                float(
                    snapshot.get("cache_hits", 0)
                ),
                metric_type="counter",
                unit="",
            )
        )
        points.append(
            self._make_point(
                "redis_cache_miss_total",
                float(
                    snapshot.get("cache_misses", 0)
                ),
                metric_type="counter",
                unit="",
            )
        )
        points.append(
            self._make_point(
                "redis_cache_hit_ratio",
                float(
                    snapshot.get("cache_hit_ratio", 0.0)
                ),
                metric_type="gauge",
                unit="",
            )
        )

        # Command metrics
        points.append(
            self._make_point(
                "redis_commands_total",
                float(
                    snapshot.get("commands", 0)
                ),
                metric_type="counter",
                unit="",
            )
        )
        points.append(
            self._make_point(
                "redis_failed_total",
                float(
                    snapshot.get("failed_commands", 0)
                ),
                metric_type="counter",
                unit="",
            )
        )

        # Message throughput
        points.append(
            self._make_point(
                "redis_published_total",
                float(
                    snapshot.get("published_messages", 0)
                ),
                metric_type="counter",
                unit="",
            )
        )
        points.append(
            self._make_point(
                "redis_consumed_total",
                float(
                    snapshot.get("consumed_messages", 0)
                ),
                metric_type="counter",
                unit="",
            )
        )

        # Latency
        points.append(
            self._make_point(
                "redis_latency_ms",
                float(
                    snapshot.get("average_latency_ms", 0.0)
                ),
                metric_type="gauge",
                unit="ms",
            )
        )

        return points