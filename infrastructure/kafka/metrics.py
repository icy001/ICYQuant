"""
Kafka producer and consumer metrics.

Provides data classes for tracking Kafka
operation statistics and performance metrics
for both producer and consumer.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict


class KafkaMetricsExporter:
    """
    Export Kafka runtime metrics.

    Converts internal metrics tracking
    into a format compatible with Prometheus
    and other monitoring systems.
    """

    def export_producer(
        self,
        metrics: ProducerMetrics,
    ) -> Dict[str, float]:
        """
        Export producer metrics as flat dictionary.

        Args:
            metrics: Producer metrics data class.

        Returns:
            Dictionary of metric name to value.
        """

        return {
            "kafka_producer_messages_total": (
                float(metrics.published_messages)
            ),
            "kafka_producer_failed_total": (
                float(metrics.failed_messages)
            ),
            "kafka_producer_retries_total": (
                float(metrics.retries)
            ),
            "kafka_producer_latency_ms": (
                metrics.average_latency_ms
            ),
            "kafka_producer_bytes_total": (
                float(metrics.bytes_sent)
            ),
        }

    def export_consumer(
        self,
        metrics: ConsumerMetrics,
    ) -> Dict[str, float]:
        """
        Export consumer metrics as flat dictionary.

        Args:
            metrics: Consumer metrics data class.

        Returns:
            Dictionary of metric name to value.
        """

        return {
            "kafka_consumer_messages_total": (
                float(metrics.consumed_messages)
            ),
            "kafka_consumer_failed_total": (
                float(metrics.failed_messages)
            ),
            "kafka_consumer_rebalance_total": (
                float(metrics.rebalance_count)
            ),
            "kafka_consumer_latency_ms": (
                metrics.average_latency_ms
            ),
            "kafka_consumer_bytes_total": (
                float(metrics.bytes_received)
            ),
        }

    def export_all(
        self,
        producer: ProducerMetrics,
        consumer: ConsumerMetrics,
    ) -> Dict[str, float]:
        """
        Export all Kafka metrics.

        Args:
            producer: Producer metrics.
            consumer: Consumer metrics.

        Returns:
            Combined metrics dictionary.
        """

        result = self.export_producer(producer)
        result.update(self.export_consumer(consumer))
        return result


@dataclass
class ConsumerMetrics:
    """
    Kafka consumer metrics.

    Tracks message consumption counts,
    offset commits, rebalance events,
    and data volume for monitoring.
    """

    consumed_messages: int = 0

    committed_offsets: int = 0

    failed_messages: int = 0

    rebalance_count: int = 0

    average_latency_ms: float = 0.0

    bytes_received: int = 0

    def record_consumed(
        self,
        byte_count: int,
        latency_ms: float,
    ) -> None:
        """
        Record a successful consume and commit.

        Args:
            byte_count: Number of bytes received.
            latency_ms: End-to-end processing latency.
        """

        self.consumed_messages += 1
        self.committed_offsets += 1
        self.bytes_received += byte_count

        if self.consumed_messages > 0:
            total = (
                self.average_latency_ms
                * (self.consumed_messages - 1)
            )
            self.average_latency_ms = round(
                (total + latency_ms)
                / self.consumed_messages,
                3,
            )

    def record_failure(
        self,
    ) -> None:
        """
        Record a failed message processing.
        """

        self.failed_messages += 1

    def record_rebalance(
        self,
    ) -> None:
        """
        Record a consumer group rebalance.
        """

        self.rebalance_count += 1

    def snapshot(
        self,
    ) -> dict[str, object]:
        """
        Return metrics snapshot as dictionary.

        Returns:
            Dictionary of all metrics.
        """

        total = (
            self.consumed_messages
            + self.failed_messages
        )

        return {
            "consumed_messages": (
                self.consumed_messages
            ),
            "committed_offsets": (
                self.committed_offsets
            ),
            "failed_messages": (
                self.failed_messages
            ),
            "rebalance_count": (
                self.rebalance_count
            ),
            "average_latency_ms": (
                self.average_latency_ms
            ),
            "bytes_received": (
                self.bytes_received
            ),
            "success_rate": (
                round(
                    self.consumed_messages
                    / max(total, 1),
                    4,
                )
            ),
        }


@dataclass
class ProducerMetrics:
    """
    Kafka producer metrics.

    Tracks message publication counts,
    retries, latency, and data volume
    for monitoring and observability.
    """

    published_messages: int = 0

    failed_messages: int = 0

    retries: int = 0

    average_latency_ms: float = 0.0

    bytes_sent: int = 0

    def record_success(
        self,
        byte_count: int,
        latency_ms: float,
    ) -> None:
        """
        Record a successful publish.

        Args:
            byte_count: Number of bytes sent.
            latency_ms: End-to-end latency in ms.
        """

        self.published_messages += 1
        self.bytes_sent += byte_count

        if self.published_messages > 0:
            total = (
                self.average_latency_ms
                * (self.published_messages - 1)
            )
            self.average_latency_ms = round(
                (total + latency_ms)
                / self.published_messages,
                3,
            )

    def record_failure(
        self,
    ) -> None:
        """
        Record a failed publish.
        """

        self.failed_messages += 1

    def record_retry(
        self,
    ) -> None:
        """
        Record a retry attempt.
        """

        self.retries += 1

    def snapshot(
        self,
    ) -> dict[str, object]:
        """
        Return metrics snapshot as dictionary.

        Returns:
            Dictionary of all metrics.
        """

        return {
            "published_messages": (
                self.published_messages
            ),
            "failed_messages": (
                self.failed_messages
            ),
            "retries": self.retries,
            "average_latency_ms": (
                self.average_latency_ms
            ),
            "bytes_sent": self.bytes_sent,
            "success_rate": (
                round(
                    self.published_messages
                    / max(
                        self.published_messages
                        + self.failed_messages,
                        1,
                    ),
                    4,
                )
            ),
        }
