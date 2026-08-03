"""
Redis runtime metrics.

Provides data class for tracking Redis
operation statistics and performance metrics.
"""

from __future__ import annotations

from dataclasses import dataclass, field


class RedisMetricsExporter:
    """
    Export Redis runtime metrics.

    Converts internal metrics tracking
    into a format compatible with Prometheus
    and other monitoring systems.
    """

    def export(
        self,
        metrics: RedisMetrics,
    ) -> dict[str, float]:
        """
        Export metrics as flat dictionary.

        Args:
            metrics: Redis metrics data class.

        Returns:
            Dictionary of metric name to value.
        """

        return {
            "redis_commands_total": (
                float(metrics.commands)
            ),
            "redis_failed_total": (
                float(metrics.failed_commands)
            ),
            "redis_cache_hits_total": (
                float(metrics.cache_hits)
            ),
            "redis_cache_misses_total": (
                float(metrics.cache_misses)
            ),
            "redis_latency_ms": (
                metrics.average_latency_ms
            ),
        }


@dataclass
class RedisMetrics:
    """
    Redis runtime metrics.

    Tracks command counts, cache statistics,
    and performance indicators for monitoring
    and observability.
    """

    commands: int = 0

    failed_commands: int = 0

    published_messages: int = 0

    consumed_messages: int = 0

    cache_hits: int = 0

    cache_misses: int = 0

    average_latency_ms: float = 0.0

    def record_command(
        self,
        failed: bool = False,
    ) -> None:
        """
        Record a command execution.

        Args:
            failed: Whether the command failed.
        """

        self.commands += 1

        if failed:
            self.failed_commands += 1

    def record_publish(
        self,
        count: int = 1,
    ) -> None:
        """
        Record published messages.

        Args:
            count: Number of messages published.
        """

        self.published_messages += count

    def record_consume(
        self,
        count: int = 1,
    ) -> None:
        """
        Record consumed messages.

        Args:
            count: Number of messages consumed.
        """

        self.consumed_messages += count

    def record_cache(
        self,
        hit: bool,
    ) -> None:
        """
        Record cache hit/miss.

        Args:
            hit: Whether the lookup was a hit.
        """

        if hit:
            self.cache_hits += 1
        else:
            self.cache_misses += 1

    def record_latency(
        self,
        latency_ms: float,
    ) -> None:
        """
        Record command latency.

        Args:
            latency_ms: Command latency in milliseconds.
        """

        if self.commands > 0:
            total = (
                self.average_latency_ms
                * (self.commands - 1)
            )
            self.average_latency_ms = round(
                (total + latency_ms) / self.commands,
                3,
            )

    def snapshot(
        self,
    ) -> dict[str, object]:
        """
        Return metrics snapshot as dictionary.

        Returns:
            Dictionary of all metrics.
        """

        return {
            "commands": self.commands,
            "failed_commands": self.failed_commands,
            "published_messages": self.published_messages,
            "consumed_messages": self.consumed_messages,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "cache_hit_ratio": (
                round(
                    self.cache_hits
                    / max(
                        self.cache_hits
                        + self.cache_misses,
                        1,
                    ),
                    4,
                )
            ),
            "average_latency_ms": (
                self.average_latency_ms
            ),
        }