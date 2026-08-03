"""
Database metrics collector.

Collects metrics from the DatabaseEngine
including connection pool statistics,
query latency, and health indicators.

Usage:
    from infrastructure.monitoring.collectors import DatabaseCollector
    collector = DatabaseCollector(database_engine)
    registry.add_collector("database", collector)
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..collector import BaseCollector
from ..models import MetricPoint


class DatabaseCollector(BaseCollector):
    """
    Database metrics collector.

    Collects connection pool metrics, query
    latency, and database health from a
    DatabaseEngine instance.

    Metrics:
    - icyquant_database_pool_size: Total pool size
    - icyquant_database_active_connections: Checked out
    - icyquant_database_idle_connections: Checked in
    - icyquant_database_pool_overflow: Overflow connections
    - icyquant_database_uptime_seconds: Engine uptime
    - icyquant_database_initialized: Engine ready
    """

    def __init__(
        self,
        database: Optional[Any] = None,
        labels: Optional[Dict[str, str]] = None,
    ) -> None:
        """
        Initialize database collector.

        Args:
            database: DatabaseEngine instance.
            labels: Additional labels for all metrics.
        """

        super().__init__(
            name="database",
            namespace="icyquant",
            labels=labels,
        )
        self._database = database

    @property
    def is_available(
        self,
    ) -> bool:
        """Check if database engine is available."""
        return self._database is not None

    async def collect(
        self,
    ) -> List[MetricPoint]:
        """
        Collect database metrics.

        Returns:
            List of MetricPoint objects.
        """

        points: List[MetricPoint] = []

        if self._database is None:
            return points

        try:
            pool_stats = self._database.pool_statistics()
            points.append(
                self._make_point(
                    "database_pool_size",
                    float(
                        pool_stats.get("size", 0)
                    ),
                    metric_type="gauge",
                    unit="",
                )
            )
            points.append(
                self._make_point(
                    "database_active_connections",
                    float(
                        pool_stats.get("checked_out", 0)
                    ),
                    metric_type="gauge",
                    unit="",
                )
            )
            points.append(
                self._make_point(
                    "database_idle_connections",
                    float(
                        pool_stats.get("checked_in", 0)
                    ),
                    metric_type="gauge",
                    unit="",
                )
            )
            points.append(
                self._make_point(
                    "database_pool_overflow",
                    float(
                        pool_stats.get("overflow", 0)
                    ),
                    metric_type="gauge",
                    unit="",
                )
            )
        except Exception:
            pass

        try:
            stats = self._database.statistics()
            points.append(
                self._make_point(
                    "database_initialized",
                    float(
                        1.0
                        if stats.get("initialized", False)
                        else 0.0
                    ),
                    metric_type="gauge",
                    unit="",
                )
            )
            uptime = stats.get("uptime_seconds")
            if uptime is not None:
                points.append(
                    self._make_point(
                        "database_uptime_seconds",
                        float(uptime),
                        metric_type="gauge",
                        unit="seconds",
                    )
                )
        except Exception:
            pass

        return points