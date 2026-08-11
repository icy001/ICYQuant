"""
Streaming Metrics — Prometheus-style metrics for the real-time
streaming platform covering events, processing, checkpointing,
exactly-once, DLQ, backpressure, and window processing.

Commit 16 Part 1.4
"""

from __future__ import annotations

import logging
import time
from typing import Any

logger = logging.getLogger(__name__)


class StreamingMetrics:
    """
    Prometheus-style metrics for the streaming platform.

    Tracks:
        icyquant_stream_events_total
        icyquant_stream_processing_latency
        icyquant_stream_checkpoint_total
        icyquant_stream_exactly_once_total
        icyquant_stream_dlq_total
        icyquant_stream_backpressure_total
        icyquant_stream_window_processing_total

    Usage::

        metrics = StreamingMetrics()
        metrics.record_event("market.tick", "published")
        metrics.record_processing_latency("market.tick", 5.2)
        metrics.record_dlq("market.tick", "deserialization_error")
    """

    PREFIX = "icyquant_stream"

    def __init__(self) -> None:
        self._counters: dict[str, float] = {}
        self._gauges: dict[str, float] = {}
        self._histograms: dict[str, list[float]] = {}

        # Event counters
        self._counters[f"{self.PREFIX}_events_total"] = 0.0
        self._counters[f"{self.PREFIX}_events_published"] = 0.0
        self._counters[f"{self.PREFIX}_events_consumed"] = 0.0
        self._counters[f"{self.PREFIX}_events_dropped"] = 0.0
        self._counters[f"{self.PREFIX}_events_late"] = 0.0

        # Processing counters
        self._counters[f"{self.PREFIX}_processing_total"] = 0.0
        self._counters[f"{self.PREFIX}_processing_errors"] = 0.0
        self._counters[f"{self.PREFIX}_topics_created"] = 0.0
        self._counters[f"{self.PREFIX}_topics_deleted"] = 0.0
        self._counters[f"{self.PREFIX}_subscriptions_total"] = 0.0

        # Checkpoint counters
        self._counters[f"{self.PREFIX}_checkpoint_total"] = 0.0
        self._counters[f"{self.PREFIX}_checkpoint_restores"] = 0.0

        # Exactly-once counters
        self._counters[f"{self.PREFIX}_exactly_once_total"] = 0.0
        self._counters[f"{self.PREFIX}_exactly_once_duplicates"] = 0.0

        # DLQ counters
        self._counters[f"{self.PREFIX}_dlq_total"] = 0.0
        self._counters[f"{self.PREFIX}_dlq_replayed"] = 0.0
        self._counters[f"{self.PREFIX}_dlq_discarded"] = 0.0

        # Backpressure counters
        self._counters[f"{self.PREFIX}_backpressure_total"] = 0.0
        self._counters[f"{self.PREFIX}_backpressure_dropped"] = 0.0

        # Window counters
        self._counters[f"{self.PREFIX}_window_processing_total"] = 0.0
        self._counters[f"{self.PREFIX}_window_emitted"] = 0.0

        # Histograms
        self._histograms[f"{self.PREFIX}_processing_latency"] = []
        self._histograms[f"{self.PREFIX}_publish_latency"] = []
        self._histograms[f"{self.PREFIX}_checkpoint_latency"] = []
        self._histograms[f"{self.PREFIX}_window_latency"] = []

        # Gauges
        self._gauges[f"{self.PREFIX}_active_subscriptions"] = 0.0
        self._gauges[f"{self.PREFIX}_active_windows"] = 0.0
        self._gauges[f"{self.PREFIX}_queue_depth"] = 0.0
        self._gauges[f"{self.PREFIX}_dlq_depth"] = 0.0
        self._gauges[f"{self.PREFIX}_backpressure_active"] = 0.0

    # ── Event Metrics ─────────────────────────────────────────────

    def record_event(self, topic: str, action: str) -> None:
        """Record a stream event."""
        self._counters[f"{self.PREFIX}_events_total"] += 1
        if action == "published":
            self._counters[f"{self.PREFIX}_events_published"] += 1
        elif action == "consumed":
            self._counters[f"{self.PREFIX}_events_consumed"] += 1
        elif action == "dropped":
            self._counters[f"{self.PREFIX}_events_dropped"] += 1
        elif action == "late":
            self._counters[f"{self.PREFIX}_events_late"] += 1

    def record_publish(self, topic: str, success: bool) -> None:
        """Record a publish event."""
        self._counters[f"{self.PREFIX}_events_total"] += 1
        self._counters[f"{self.PREFIX}_events_published"] += 1
        if not success:
            self._counters[f"{self.PREFIX}_processing_errors"] += 1

    def record_topic_created(self, topic: str) -> None:
        """Record topic creation."""
        self._counters[f"{self.PREFIX}_topics_created"] += 1

    def record_topic_deleted(self, topic: str) -> None:
        """Record topic deletion."""
        self._counters[f"{self.PREFIX}_topics_deleted"] += 1

    def record_subscription(self, topic: str, action: str) -> None:
        """Record subscription event."""
        if action == "subscribe":
            self._counters[f"{self.PREFIX}_subscriptions_total"] += 1
            self._gauges[f"{self.PREFIX}_active_subscriptions"] += 1
        elif action == "unsubscribe":
            self._gauges[f"{self.PREFIX}_active_subscriptions"] = max(
                0, self._gauges[f"{self.PREFIX}_active_subscriptions"] - 1,
            )

    # ── Processing Metrics ────────────────────────────────────────

    def record_processing(self, topic: str, latency_ms: float) -> None:
        """Record event processing."""
        self._counters[f"{self.PREFIX}_processing_total"] += 1
        self._histograms[f"{self.PREFIX}_processing_latency"].append(latency_ms)

    def record_processing_error(self, topic: str, error: str = "") -> None:
        """Record processing error."""
        self._counters[f"{self.PREFIX}_processing_errors"] += 1

    # ── Checkpoint Metrics ────────────────────────────────────────

    def record_checkpoint(self, topic: str, latency_ms: float = 0) -> None:
        """Record a checkpoint."""
        self._counters[f"{self.PREFIX}_checkpoint_total"] += 1
        if latency_ms > 0:
            self._histograms[f"{self.PREFIX}_checkpoint_latency"].append(latency_ms)

    def record_checkpoint_restore(self, topic: str) -> None:
        """Record a checkpoint restore."""
        self._counters[f"{self.PREFIX}_checkpoint_restores"] += 1

    # ── Exactly-Once Metrics ──────────────────────────────────────

    def record_exactly_once(self, topic: str) -> None:
        """Record exactly-once processing."""
        self._counters[f"{self.PREFIX}_exactly_once_total"] += 1

    def record_duplicate_detected(self, topic: str) -> None:
        """Record a duplicate event."""
        self._counters[f"{self.PREFIX}_exactly_once_duplicates"] += 1

    # ── DLQ Metrics ───────────────────────────────────────────────

    def record_dlq(self, topic: str, error: str = "") -> None:
        """Record a DLQ entry."""
        self._counters[f"{self.PREFIX}_dlq_total"] += 1
        self._gauges[f"{self.PREFIX}_dlq_depth"] += 1

    def record_dlq_replayed(self, topic: str) -> None:
        """Record a DLQ replay."""
        self._counters[f"{self.PREFIX}_dlq_replayed"] += 1
        self._gauges[f"{self.PREFIX}_dlq_depth"] = max(
            0, self._gauges[f"{self.PREFIX}_dlq_depth"] - 1,
        )

    def record_dlq_discarded(self, topic: str) -> None:
        """Record a DLQ discard."""
        self._counters[f"{self.PREFIX}_dlq_discarded"] += 1
        self._gauges[f"{self.PREFIX}_dlq_depth"] = max(
            0, self._gauges[f"{self.PREFIX}_dlq_depth"] - 1,
        )

    # ── Backpressure Metrics ──────────────────────────────────────

    def record_backpressure(self, topic: str, dropped: int = 0) -> None:
        """Record backpressure event."""
        self._counters[f"{self.PREFIX}_backpressure_total"] += 1
        self._counters[f"{self.PREFIX}_backpressure_dropped"] += dropped

    def set_backpressure_active(self, count: int) -> None:
        """Set active backpressure gauge."""
        self._gauges[f"{self.PREFIX}_backpressure_active"] = float(count)

    # ── Window Metrics ────────────────────────────────────────────

    def record_window_processing(self, window_type: str, latency_ms: float = 0) -> None:
        """Record window processing."""
        self._counters[f"{self.PREFIX}_window_processing_total"] += 1
        if latency_ms > 0:
            self._histograms[f"{self.PREFIX}_window_latency"].append(latency_ms)

    def record_window_emitted(self, window_type: str, count: int = 1) -> None:
        """Record window emission."""
        self._counters[f"{self.PREFIX}_window_emitted"] += count

    # ── Gauge Updates ─────────────────────────────────────────────

    def set_queue_depth(self, depth: int) -> None:
        """Set current queue depth."""
        self._gauges[f"{self.PREFIX}_queue_depth"] = float(depth)

    def set_active_windows(self, count: int) -> None:
        """Set active windows count."""
        self._gauges[f"{self.PREFIX}_active_windows"] = float(count)

    # ── Histogram Stats ───────────────────────────────────────────

    def _histogram_stats(self, name: str) -> dict[str, float]:
        """Compute histogram statistics."""
        values = self._histograms.get(name, [])
        if not values:
            return {"count": 0, "sum": 0.0, "avg": 0.0, "min": 0.0, "max": 0.0, "p50": 0.0, "p95": 0.0, "p99": 0.0}

        sorted_vals = sorted(values)
        n = len(sorted_vals)
        return {
            "count": n,
            "sum": sum(sorted_vals),
            "avg": sum(sorted_vals) / n,
            "min": min(sorted_vals),
            "max": max(sorted_vals),
            "p50": sorted_vals[int(n * 0.50)] if n > 1 else sorted_vals[0],
            "p95": sorted_vals[int(n * 0.95)] if n > 1 else sorted_vals[0],
            "p99": sorted_vals[int(n * 0.99)] if n > 1 else sorted_vals[0],
        }

    def to_dict(self) -> dict[str, Any]:
        """Serialize all metrics."""
        return {
            "counters": dict(self._counters),
            "gauges": dict(self._gauges),
            "histograms": {
                k.replace(self.PREFIX + "_", ""): self._histogram_stats(k)
                for k in self._histograms
            },
        }
