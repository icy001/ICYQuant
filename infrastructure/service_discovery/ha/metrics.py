"""HA metrics collection for ICYQuant service discovery HA.

Provides ``HAMetrics`` for recording and querying HA-related
metrics including failovers, self-healing, registry recovery,
replica promotions, traffic drains, rebalances, and split-brain
detection.

Metric names follow the ``icyquant_*`` naming convention.
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

METRIC_FAILOVER = "icyquant_failover_total"
METRIC_SELF_HEALING = "icyquant_self_healing_total"
METRIC_REGISTRY_RECOVERY = "icyquant_registry_recovery_total"
METRIC_REPLICA_PROMOTION = "icyquant_replica_promotion_total"
METRIC_TRAFFIC_DRAIN = "icyquant_traffic_drain_seconds"
METRIC_CLUSTER_REBALANCE = "icyquant_cluster_rebalance_total"
METRIC_SPLIT_BRAIN = "icyquant_split_brain_detected_total"


class HAMetrics:
    """Collects and exposes HA-related metrics.

    Maintains counters, timers, and events for all HA
    operations.  Metrics can be snapshot'd for downstream
    monitoring or alerting systems.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._counters: Dict[str, int] = {
            METRIC_FAILOVER: 0,
            METRIC_SELF_HEALING: 0,
            METRIC_REGISTRY_RECOVERY: 0,
            METRIC_REPLICA_PROMOTION: 0,
            METRIC_TRAFFIC_DRAIN: 0.0,
            METRIC_CLUSTER_REBALANCE: 0,
            METRIC_SPLIT_BRAIN: 0,
        }
        self._labels: Dict[str, Dict[str, int]] = {}
        self._timers: Dict[str, List[float]] = {}
        self._events: List[Dict[str, Any]] = []
        self._max_events = 500
        self._record_count = 0

    # ── Helpers ──

    @staticmethod
    def _now_iso() -> str:
        return datetime.utcnow().isoformat()

    def _increment_counter(
        self, name: str, labels: Optional[Dict[str, str]] = None
    ) -> None:
        self._counters[name] = self._counters.get(name, 0) + 1
        if labels:
            label_key = ",".join(
                f"{k}={v}" for k, v in sorted(labels.items())
            )
            self._labels.setdefault(name, {})
            self._labels[name][label_key] = (
                self._labels[name].get(label_key, 0) + 1
            )

    def _record_timer(self, name: str, duration: float) -> None:
        self._timers.setdefault(name, [])
        self._timers[name].append(float(duration))
        max_timers = 1000
        if len(self._timers[name]) > max_timers:
            self._timers[name] = self._timers[name][-max_timers:]

    def _add_event(
        self, event_type: str, details: Dict[str, Any]
    ) -> None:
        self._events.append(
            {
                "event_type": event_type,
                "details": details,
                "timestamp": self._now_iso(),
            }
        )
        if len(self._events) > self._max_events:
            excess = len(self._events) - self._max_events
            del self._events[:excess]

    # ── Public API ──

    def record_failover(
        self,
        service_name: str,
        success: bool,
        duration: float,
    ) -> None:
        """Record a failover event.

        Args:
            service_name: The affected service.
            success: Whether the failover succeeded.
            duration: Duration in seconds.
        """
        with self._lock:
            self._record_count += 1
            self._increment_counter(
                METRIC_FAILOVER,
                {"service": service_name, "success": str(success)},
            )
            self._record_timer(METRIC_FAILOVER, duration)
            self._add_event(
                "failover",
                {
                    "service_name": service_name,
                    "success": success,
                    "duration": duration,
                },
            )

    def record_self_healing(
        self,
        failure_type: str,
        service_name: str,
        success: bool,
    ) -> None:
        """Record a self-healing event.

        Args:
            failure_type: The type of failure healed.
            service_name: The affected service.
            success: Whether healing succeeded.
        """
        with self._lock:
            self._record_count += 1
            self._increment_counter(
                METRIC_SELF_HEALING,
                {
                    "failure_type": failure_type,
                    "service": service_name,
                    "success": str(success),
                },
            )
            self._add_event(
                "self_healing",
                {
                    "failure_type": failure_type,
                    "service_name": service_name,
                    "success": success,
                },
            )

    def record_registry_recovery(
        self, success: bool, duration: float
    ) -> None:
        """Record a registry recovery event.

        Args:
            success: Whether recovery succeeded.
            duration: Duration in seconds.
        """
        with self._lock:
            self._record_count += 1
            self._increment_counter(
                METRIC_REGISTRY_RECOVERY, {"success": str(success)}
            )
            self._record_timer(METRIC_REGISTRY_RECOVERY, duration)
            self._add_event(
                "registry_recovery",
                {"success": success, "duration": duration},
            )

    def record_replica_promotion(
        self, service_name: str, success: bool
    ) -> None:
        """Record a replica promotion event.

        Args:
            service_name: The affected service.
            success: Whether promotion succeeded.
        """
        with self._lock:
            self._record_count += 1
            self._increment_counter(
                METRIC_REPLICA_PROMOTION,
                {"service": service_name, "success": str(success)},
            )
            self._add_event(
                "replica_promotion",
                {
                    "service_name": service_name,
                    "success": success,
                },
            )

    def record_traffic_drain(
        self, service_name: str, duration: float
    ) -> None:
        """Record a traffic drain event.

        Args:
            service_name: The affected service.
            duration: Duration in seconds.
        """
        with self._lock:
            self._record_count += 1
            self._counters[METRIC_TRAFFIC_DRAIN] = (
                self._counters.get(METRIC_TRAFFIC_DRAIN, 0.0)
                + float(duration)
            )
            self._record_timer(METRIC_TRAFFIC_DRAIN, duration)
            self._add_event(
                "traffic_drain",
                {
                    "service_name": service_name,
                    "duration": duration,
                },
            )

    def record_cluster_rebalance(
        self, success: bool, instance_count: int
    ) -> None:
        """Record a cluster rebalance event.

        Args:
            success: Whether rebalance succeeded.
            instance_count: Number of instances involved.
        """
        with self._lock:
            self._record_count += 1
            self._increment_counter(
                METRIC_CLUSTER_REBALANCE,
                {"success": str(success), "instances": str(instance_count)},
            )
            self._add_event(
                "cluster_rebalance",
                {
                    "success": success,
                    "instance_count": instance_count,
                },
            )

    def record_split_brain_detected(self, node_count: int) -> None:
        """Record a split-brain detection event.

        Args:
            node_count: Number of nodes involved.
        """
        with self._lock:
            self._record_count += 1
            self._increment_counter(
                METRIC_SPLIT_BRAIN,
                {"nodes": str(node_count)},
            )
            self._add_event(
                "split_brain_detected",
                {"node_count": node_count},
            )

    def snapshot(self) -> Dict[str, Any]:
        """Return a point-in-time snapshot of all metrics.

        Returns:
            A dictionary with counter values, label
            breakdowns, timer summaries, and recent events.
        """
        with self._lock:
            counters = dict(self._counters)
            labels_copy = {
                k: dict(v) for k, v in self._labels.items()
            }
            timer_summaries: Dict[str, Dict[str, float]] = {}
            for name, values in self._timers.items():
                if values:
                    sorted_vals = sorted(values)
                    count = len(sorted_vals)
                    avg = sum(sorted_vals) / count
                    p50 = sorted_vals[int(count * 0.5)]
                    p95 = sorted_vals[int(count * 0.95)]
                    p99 = sorted_vals[int(count * 0.99)]
                    timer_summaries[name] = {
                        "count": float(count),
                        "avg": avg,
                        "p50": p50,
                        "p95": p95,
                        "p99": p99,
                        "min": sorted_vals[0],
                        "max": sorted_vals[-1],
                    }
                else:
                    timer_summaries[name] = {
                        "count": 0.0,
                        "avg": 0.0,
                        "p50": 0.0,
                        "p95": 0.0,
                        "p99": 0.0,
                        "min": 0.0,
                        "max": 0.0,
                    }

            recent_events = list(
                self._events[-min(50, len(self._events)) :]
            )

            return {
                "counters": counters,
                "labels": labels_copy,
                "timers": timer_summaries,
                "recent_events": recent_events,
                "timestamp": self._now_iso(),
            }

    def reset(self) -> None:
        """Reset all metrics to zero."""
        with self._lock:
            for key in self._counters:
                self._counters[key] = 0 if isinstance(
                    self._counters[key], int
                ) else 0.0
            self._labels.clear()
            self._timers.clear()
            self._events.clear()
            self._record_count = 0
        logger.info("HAMetrics reset.")

    def get_stats(self) -> Dict[str, Any]:
        """Return summary statistics for the metrics collector."""
        with self._lock:
            return {
                "record_count": self._record_count,
                "counters": dict(self._counters),
                "label_counts": {
                    k: len(v) for k, v in self._labels.items()
                },
                "timer_count": len(self._timers),
                "event_count": len(self._events),
                "max_events": self._max_events,
            }

    def __repr__(self) -> str:
        with self._lock:
            return (
                f"HAMetrics(records={self._record_count}, "
                f"events={len(self._events)})"
            )