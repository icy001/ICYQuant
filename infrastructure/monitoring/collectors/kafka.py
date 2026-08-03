"""
Kafka metrics collector.

Collects producer and consumer metrics
from Kafka ProducerMetrics and
ConsumerMetrics instances.

Usage:
    from infrastructure.monitoring.collectors import KafkaCollector
    collector = KafkaCollector(producer_metrics, consumer_metrics)
    registry.add_collector("kafka", collector)
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..collector import BaseCollector
from ..models import MetricPoint


class KafkaCollector(BaseCollector):
    """
    Kafka metrics collector.

    Collects producer throughput, consumer
    lag, retry counts, and dead letter
    queue metrics from Kafka metric
    instances.

    Metrics:
    - icyquant_kafka_producer_messages_total: Published
    - icyquant_kafka_producer_failed_total: Failed publishes
    - icyquant_kafka_producer_retries_total: Retries
    - icyquant_kafka_producer_bytes_total: Bytes sent
    - icyquant_kafka_producer_latency_ms: Producer latency
    - icyquant_kafka_consumer_messages_total: Consumed
    - icyquant_kafka_consumer_failed_total: Failed consumes
    - icyquant_kafka_consumer_committed_total: Committed
    - icyquant_kafka_consumer_rebalance_total: Rebalances
    - icyquant_kafka_consumer_latency_ms: Consumer latency
    - icyquant_kafka_consumer_success_rate: Success rate
    """

    def __init__(
        self,
        producer_metrics: Optional[Any] = None,
        consumer_metrics: Optional[Any] = None,
        labels: Optional[Dict[str, str]] = None,
    ) -> None:
        """
        Initialize Kafka collector.

        Args:
            producer_metrics: ProducerMetrics instance.
            consumer_metrics: ConsumerMetrics instance.
            labels: Additional labels for all metrics.
        """

        super().__init__(
            name="kafka",
            namespace="icyquant",
            labels=labels,
        )
        self._producer = producer_metrics
        self._consumer = consumer_metrics

    @property
    def is_available(
        self,
    ) -> bool:
        """Check if any Kafka metrics are available."""
        return (
            self._producer is not None
            or self._consumer is not None
        )

    async def collect(
        self,
    ) -> List[MetricPoint]:
        """
        Collect Kafka metrics.

        Returns:
            List of MetricPoint objects.
        """

        points: List[MetricPoint] = []

        # Producer metrics
        if self._producer is not None:
            try:
                snap = self._producer.snapshot()

                points.append(
                    self._make_point(
                        "kafka_producer_messages_total",
                        float(
                            snap.get(
                                "published_messages", 0
                            )
                        ),
                        metric_type="counter",
                        unit="",
                    )
                )
                points.append(
                    self._make_point(
                        "kafka_producer_failed_total",
                        float(
                            snap.get(
                                "failed_messages", 0
                            )
                        ),
                        metric_type="counter",
                        unit="",
                    )
                )
                points.append(
                    self._make_point(
                        "kafka_producer_retries_total",
                        float(
                            snap.get("retries", 0)
                        ),
                        metric_type="counter",
                        unit="",
                    )
                )
                points.append(
                    self._make_point(
                        "kafka_producer_bytes_total",
                        float(
                            snap.get(
                                "bytes_sent", 0
                            )
                        ),
                        metric_type="counter",
                        unit="bytes",
                    )
                )
                points.append(
                    self._make_point(
                        "kafka_producer_latency_ms",
                        float(
                            snap.get(
                                "average_latency_ms",
                                0.0,
                            )
                        ),
                        metric_type="gauge",
                        unit="ms",
                    )
                )
                points.append(
                    self._make_point(
                        "kafka_producer_success_rate",
                        float(
                            snap.get(
                                "success_rate", 0.0
                            )
                        ),
                        metric_type="gauge",
                        unit="",
                    )
                )
            except Exception:
                pass

        # Consumer metrics
        if self._consumer is not None:
            try:
                snap = self._consumer.snapshot()

                points.append(
                    self._make_point(
                        "kafka_consumer_messages_total",
                        float(
                            snap.get(
                                "consumed_messages", 0
                            )
                        ),
                        metric_type="counter",
                        unit="",
                    )
                )
                points.append(
                    self._make_point(
                        "kafka_consumer_failed_total",
                        float(
                            snap.get(
                                "failed_messages", 0
                            )
                        ),
                        metric_type="counter",
                        unit="",
                    )
                )
                points.append(
                    self._make_point(
                        "kafka_consumer_committed_total",
                        float(
                            snap.get(
                                "committed_offsets", 0
                            )
                        ),
                        metric_type="counter",
                        unit="",
                    )
                )
                points.append(
                    self._make_point(
                        "kafka_consumer_rebalance_total",
                        float(
                            snap.get(
                                "rebalance_count", 0
                            )
                        ),
                        metric_type="counter",
                        unit="",
                    )
                )
                points.append(
                    self._make_point(
                        "kafka_consumer_latency_ms",
                        float(
                            snap.get(
                                "average_latency_ms",
                                0.0,
                            )
                        ),
                        metric_type="gauge",
                        unit="ms",
                    )
                )
                points.append(
                    self._make_point(
                        "kafka_consumer_success_rate",
                        float(
                            snap.get(
                                "success_rate", 0.0
                            )
                        ),
                        metric_type="gauge",
                        unit="",
                    )
                )
            except Exception:
                pass

        return points