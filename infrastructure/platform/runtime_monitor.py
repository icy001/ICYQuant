"""
ICYQuant Infrastructure - Runtime Monitor

Monitors platform runtime: CPU, memory, module state, and performance metrics.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import logging
import threading
import time

logger = logging.getLogger(__name__)


@dataclass
class RuntimeMetrics:
    timestamp: datetime = field(default_factory=datetime.now)
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    memory_used_mb: float = 0.0
    thread_count: int = 0
    module_count: int = 0
    running_modules: int = 0
    event_count: int = 0
    queue_size: int = 0
    custom_metrics: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "timestamp": self.timestamp.isoformat(),
            "cpuPercent": self.cpu_percent,
            "memoryPercent": self.memory_percent,
            "memoryUsedMb": self.memory_used_mb,
            "threadCount": self.thread_count,
            "moduleCount": self.module_count,
            "runningModules": self.running_modules,
            "eventCount": self.event_count,
        }


class RuntimeMonitor:
    """
    Platform runtime monitor.

    Collects and reports runtime metrics for the platform.
    Supports custom metric registration and alerting.
    """

    def __init__(self, collection_interval: float = 1.0):
        self._collection_interval = collection_interval
        self._metrics_history: List[RuntimeMetrics] = []
        self._max_history = 1000
        self._custom_metrics: Dict[str, float] = {}
        self._metadata: Dict[str, Any] = {}
        self._running = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

    def start(self):
        """Start background metrics collection."""
        if self._running:
            return
        self._running = True
        self._monitor_thread = threading.Thread(
            target=self._collection_loop, daemon=True
        )
        self._monitor_thread.start()
        logger.info("Runtime monitor started")

    def stop(self):
        """Stop background metrics collection."""
        self._running = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)
            self._monitor_thread = None
        logger.info("Runtime monitor stopped")

    def _collection_loop(self):
        while self._running:
            try:
                self.collect_metrics()
            except Exception as e:
                logger.error(f"Metrics collection error: {e}")
            threading.Event().wait(self._collection_interval)

    def collect_metrics(
        self,
        module_count: int = 0,
        running_modules: int = 0,
        event_count: int = 0,
    ) -> RuntimeMetrics:
        """Collect a single set of runtime metrics."""
        metrics = RuntimeMetrics(
            timestamp=datetime.now(),
            thread_count=threading.active_count(),
            module_count=module_count,
            running_modules=running_modules,
            event_count=event_count,
            custom_metrics=dict(self._custom_metrics),
        )

        with self._lock:
            self._metrics_history.append(metrics)
            if len(self._metrics_history) > self._max_history:
                self._metrics_history = self._metrics_history[-self._max_history:]

        return metrics

    def record_metric(self, name: str, value: float):
        """Record a custom metric."""
        self._custom_metrics[name] = value

    def set_metadata(self, key: str, value: Any):
        """Set runtime metadata."""
        self._metadata[key] = value

    def get_latest(self) -> Optional[RuntimeMetrics]:
        with self._lock:
            return self._metrics_history[-1] if self._metrics_history else None

    def get_history(
        self,
        duration: Optional[timedelta] = None,
        limit: int = 100,
    ) -> List[RuntimeMetrics]:
        with self._lock:
            metrics = list(self._metrics_history)

        if duration:
            cutoff = datetime.now() - duration
            metrics = [m for m in metrics if m.timestamp >= cutoff]

        return metrics[-limit:]

    def get_metric_average(self, metric_name: str, last_n: int = 100) -> float:
        history = self.get_history(limit=last_n)
        if not history:
            return 0.0
        values = [m.custom_metrics.get(metric_name, 0.0) for m in history]
        return sum(values) / len(values) if values else 0.0

    def get_status(self) -> Dict[str, Any]:
        latest = self.get_latest()
        return {
            "running": self._running,
            "collectionInterval": self._collection_interval,
            "historySize": len(self._metrics_history),
            "latest": latest.to_dict() if latest else None,
            "customMetrics": dict(self._custom_metrics),
            "metadata": dict(self._metadata),
        }

    def to_dict(self) -> Dict:
        return self.get_status()
