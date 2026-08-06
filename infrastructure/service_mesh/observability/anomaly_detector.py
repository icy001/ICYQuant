"""Anomaly detector for ICYQuant Service Mesh.

Provides ``AnomalyDetector`` for detecting latency spikes, traffic
spikes, retry storms, error bursts, and memory leaks, emitting
incident events when anomalies are found.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import deque
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class AnomalyType(str):
    """Types of anomalies."""

    LATENCY_SPIKE = "latency_spike"
    TRAFFIC_SPIKE = "traffic_spike"
    RETRY_STORM = "retry_storm"
    ERROR_BURST = "error_burst"
    MEMORY_LEAK = "memory_leak"


class AnomalySeverity(str):
    """Anomaly severity levels."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class Anomaly:
    """A detected anomaly."""

    def __init__(
        self,
        anomaly_type: str,
        target: str,
        severity: str = AnomalySeverity.WARNING,
        value: float = 0.0,
        threshold: float = 0.0,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.anomaly_type = anomaly_type
        self.target = target
        self.severity = severity
        self.value = value
        self.threshold = threshold
        self.details = details or {}
        self.timestamp = datetime.utcnow()
        self.anomaly_id = f"anom-{int(time.time() * 1000)}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "anomaly_id": self.anomaly_id,
            "anomaly_type": self.anomaly_type,
            "target": self.target,
            "severity": self.severity,
            "value": self.value,
            "threshold": self.threshold,
            "details": dict(self.details),
            "timestamp": self.timestamp.isoformat(),
        }


class AnomalyDetector:
    """Detects anomalies across mesh services."""

    def __init__(
        self,
        latency_threshold_ms: float = 5000.0,
        latency_multiplier: float = 3.0,
        traffic_multiplier: float = 5.0,
        retry_threshold: int = 50,
        error_rate_threshold: float = 0.3,
        memory_growth_threshold: float = 0.9,
        window_s: float = 60.0,
        max_history: int = 500,
    ) -> None:
        self._latency_threshold_ms = latency_threshold_ms
        self._latency_multiplier = latency_multiplier
        self._traffic_multiplier = traffic_multiplier
        self._retry_threshold = retry_threshold
        self._error_rate_threshold = error_rate_threshold
        self._memory_growth_threshold = memory_growth_threshold
        self._window_s = window_s
        self._max_history = max_history
        self._lock = threading.RLock()
        self._latency_history: Dict[str, deque] = {}
        self._traffic_history: Dict[str, deque] = {}
        self._retry_counts: Dict[str, int] = {}
        self._error_counts: Dict[str, int] = {}
        self._request_counts: Dict[str, int] = {}
        self._memory_history: Dict[str, deque] = {}
        self._anomalies: List[Anomaly] = []
        self._listeners: List[Callable[[Anomaly], None]] = []
        self._detection_count = 0
        self._started = False

    @property
    def is_running(self) -> bool:
        return self._started

    def start(self) -> None:
        self._started = True
        logger.info("Anomaly detector started")

    def stop(self) -> None:
        self._started = False
        logger.info("Anomaly detector stopped")

    def add_listener(self, listener: Callable[[Anomaly], None]) -> None:
        self._listeners.append(listener)

    def record_latency(self, service: str, latency_ms: float) -> Optional[Anomaly]:
        with self._lock:
            if service not in self._latency_history:
                self._latency_history[service] = deque(maxlen=1000)
            history = self._latency_history[service]
            history.append(latency_ms)

            if len(history) < 10:
                return None

            avg = sum(history) / len(history)
            threshold = max(self._latency_threshold_ms, avg * self._latency_multiplier)
            if latency_ms > threshold:
                anomaly = Anomaly(
                    anomaly_type=AnomalyType.LATENCY_SPIKE,
                    target=service,
                    severity=AnomalySeverity.CRITICAL if latency_ms > threshold * 2 else AnomalySeverity.WARNING,
                    value=latency_ms,
                    threshold=threshold,
                    details={"avg_latency_ms": avg, "history_count": len(history)},
                )
                self._add_anomaly(anomaly)
                return anomaly
        return None

    def record_traffic(self, service: str, request_count: int = 1) -> Optional[Anomaly]:
        now = time.monotonic()
        with self._lock:
            if service not in self._traffic_history:
                self._traffic_history[service] = deque(maxlen=100)
            history = self._traffic_history[service]
            history.append((now, request_count))

            cutoff = now - self._window_s
            recent = [(t, c) for t, c in history if t >= cutoff]
            total_recent = sum(c for _, c in recent)

            if len(history) < 10:
                return None

            older = [(t, c) for t, c in history if t < cutoff]
            if not older:
                return None

            older_avg = sum(c for _, c in older) / len(older) if older else 0
            if older_avg > 0:
                multiplier = total_recent / (older_avg * len(recent) / max(len(older), 1))
                if multiplier > self._traffic_multiplier:
                    anomaly = Anomaly(
                        anomaly_type=AnomalyType.TRAFFIC_SPIKE,
                        target=service,
                        severity=AnomalySeverity.WARNING,
                        value=total_recent,
                        threshold=older_avg * self._traffic_multiplier,
                        details={"multiplier": multiplier},
                    )
                    self._add_anomaly(anomaly)
                    return anomaly
        return None

    def record_retry(self, service: str, count: int = 1) -> Optional[Anomaly]:
        with self._lock:
            self._retry_counts[service] = self._retry_counts.get(service, 0) + count
            if self._retry_counts[service] > self._retry_threshold:
                anomaly = Anomaly(
                    anomaly_type=AnomalyType.RETRY_STORM,
                    target=service,
                    severity=AnomalySeverity.CRITICAL,
                    value=self._retry_counts[service],
                    threshold=self._retry_threshold,
                    details={},
                )
                self._add_anomaly(anomaly)
                self._retry_counts[service] = 0
                return anomaly
        return None

    def record_error(self, service: str, is_error: bool) -> Optional[Anomaly]:
        with self._lock:
            self._request_counts[service] = self._request_counts.get(service, 0) + 1
            if is_error:
                self._error_counts[service] = self._error_counts.get(service, 0) + 1

            total = self._request_counts[service]
            if total < 10:
                return None

            error_rate = self._error_counts[service] / total
            if error_rate > self._error_rate_threshold:
                anomaly = Anomaly(
                    anomaly_type=AnomalyType.ERROR_BURST,
                    target=service,
                    severity=AnomalySeverity.CRITICAL,
                    value=error_rate,
                    threshold=self._error_rate_threshold,
                    details={"error_count": self._error_counts[service], "request_count": total},
                )
                self._add_anomaly(anomaly)
                self._error_counts[service] = 0
                self._request_counts[service] = 0
                return anomaly
        return None

    def record_memory(self, service: str, usage_ratio: float) -> Optional[Anomaly]:
        with self._lock:
            if service not in self._memory_history:
                self._memory_history[service] = deque(maxlen=100)
            self._memory_history[service].append(usage_ratio)

            history = self._memory_history[service]
            if len(history) < 5:
                return None

            if usage_ratio > self._memory_growth_threshold:
                growth = history[-1] - history[0]
                if growth > 0.1:
                    anomaly = Anomaly(
                        anomaly_type=AnomalyType.MEMORY_LEAK,
                        target=service,
                        severity=AnomalySeverity.CRITICAL,
                        value=usage_ratio,
                        threshold=self._memory_growth_threshold,
                        details={"growth": growth},
                    )
                    self._add_anomaly(anomaly)
                    return anomaly
        return None

    def _add_anomaly(self, anomaly: Anomaly) -> None:
        with self._lock:
            self._detection_count += 1
            self._anomalies.append(anomaly)
            if len(self._anomalies) > self._max_history:
                self._anomalies = self._anomalies[-self._max_history:]

        for listener in self._listeners:
            try:
                listener(anomaly)
            except Exception as exc:
                logger.warning("Anomaly listener failed: %s", exc)

    def get_anomalies(
        self,
        anomaly_type: Optional[str] = None,
        target: Optional[str] = None,
        severity: Optional[str] = None,
        limit: int = 100,
    ) -> List[Anomaly]:
        with self._lock:
            anomalies = list(self._anomalies)
        results = []
        for a in anomalies:
            if anomaly_type and a.anomaly_type != anomaly_type:
                continue
            if target and a.target != target:
                continue
            if severity and a.severity != severity:
                continue
            results.append(a)
        return results[-limit:]

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "running": self._started,
                "detection_count": self._detection_count,
                "anomaly_count": len(self._anomalies),
                "tracked_services": len(self._latency_history),
                "listener_count": len(self._listeners),
                "config": {
                    "latency_threshold_ms": self._latency_threshold_ms,
                    "latency_multiplier": self._latency_multiplier,
                    "traffic_multiplier": self._traffic_multiplier,
                    "retry_threshold": self._retry_threshold,
                    "error_rate_threshold": self._error_rate_threshold,
                    "memory_growth_threshold": self._memory_growth_threshold,
                },
            }

    def clear(self) -> None:
        with self._lock:
            self._latency_history.clear()
            self._traffic_history.clear()
            self._retry_counts.clear()
            self._error_counts.clear()
            self._request_counts.clear()
            self._memory_history.clear()
            self._anomalies.clear()
            self._detection_count = 0
