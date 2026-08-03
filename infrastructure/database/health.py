"""
Database health check.

Production-grade health monitoring with
connection verification, latency tracking,
pool metrics, and automatic retry.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from .engine import DatabaseEngine
from .exceptions import (
    DatabaseError,
    DatabaseHealthError,
)


@dataclass
class DatabaseHealthReport:
    """
    Database health report.

    Contains health status, latency, and
    connection pool metrics.
    """

    healthy: bool

    latency_ms: float

    message: str

    pool: dict[str, int]


class DatabaseHealth:
    """
    Production health checker.

    Performs database health verification
    with automatic retry and slow query
    detection.
    """

    def __init__(
        self,
        engine: DatabaseEngine,
    ) -> None:

        self._engine = engine

        self._slow_query_ms: float = 100

    async def check(
        self,
    ) -> tuple[bool, str]:
        """
        Execute health check.

        Returns a tuple of (healthy, message)
        for integration with Bootstrap Health Registry.
        """

        try:

            report = await self.report()

            return (
                report.healthy,
                report.message,
            )

        except DatabaseError as e:

            return (
                False,
                str(e),
            )

    async def report(
        self,
    ) -> DatabaseHealthReport:
        """
        Generate health report.

        Performs SELECT 1 with automatic retry
        on failure. Detects slow queries based
        on configured threshold.
        """

        retries = 3

        for _ in range(retries):

            try:

                latency = (
                    await self._engine.ping()
                )

                message = "OK"

                if latency > self._slow_query_ms:
                    message = (
                        "Slow Database"
                    )

                return DatabaseHealthReport(
                    healthy=True,
                    latency_ms=round(latency, 3),
                    message=message,
                    pool=(
                        self._engine
                        .pool_statistics()
                    ),
                )

            except Exception:

                await asyncio.sleep(0.5)

        raise DatabaseHealthError(
            "Database unavailable after "
            f"{retries} retries."
        )