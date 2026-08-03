"""
Redis health checker.

Provides health check implementation
for integration with the bootstrap health registry.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from .client import RedisClient


class RedisHealth:
    """
    Redis health checker.

    Performs connectivity and responsiveness
    checks against the Redis server. Integrates
    with the bootstrap health registry.
    """

    def __init__(
        self,
        client: Optional[RedisClient] = None,
    ) -> None:

        self._client = client

    async def check(
        self,
    ) -> tuple[bool, str]:
        """
        Execute health check.

        Returns a tuple of (healthy, message).
        """

        if self._client is None:
            return (
                True,
                "Not Initialized",
            )

        try:
            latency = await self._client.ping()
            return (
                True,
                f"OK ({latency:.1f}ms)",
            )
        except Exception as e:
            return (
                False,
                str(e),
            )

    async def report(
        self,
    ) -> Dict[str, Any]:
        """
        Generate health report.

        Returns a detailed health report
        including latency and client statistics.

        Returns:
            Health report dictionary.
        """

        if self._client is None:
            return {
                "healthy": True,
                "latency_ms": 0.0,
                "message": "Not Initialized",
                "client": None,
            }

        try:
            latency = await self._client.ping()
            client_stats = self._client.statistics()

            return {
                "healthy": True,
                "latency_ms": round(latency, 3),
                "message": "OK",
                "client": client_stats,
            }
        except Exception as e:
            return {
                "healthy": False,
                "latency_ms": 0.0,
                "message": str(e),
                "client": self._client.statistics(),
            }