"""Resource Monitor — continuous resource usage monitoring.

The :class:`ResourceMonitor` periodically samples CPU, memory, GPU, and IO
usage across all nodes, maintains a sliding window of metrics, and triggers
alerts when thresholds are breached.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ResourceSnapshot:
    """A single point-in-time resource sample."""

    node_id: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    cpu_pct: float = 0.0
    memory_pct: float = 0.0
    gpu_pct: float = 0.0
    disk_io_mbps: float = 0.0
    network_io_mbps: float = 0.0
    concurrency: int = 0
    queue_depth: int = 0


class ResourceMonitor:
    """Continuous resource usage monitor with alerting.

    Usage::

        monitor = ResourceMonitor(poll_interval_ms=5000)
        await monitor.start()
        # ...
        stats = monitor.get_node_stats("node-1")
    """

    def __init__(
        self, poll_interval_ms: int = 5000,
        max_history_per_node: int = 720,  # 1 hour at 5s intervals
    ) -> None:
        self._lock = threading.RLock()
        self._poll_interval_ms = poll_interval_ms
        self._max_history = max_history_per_node
        self._running = False

        self._history: Dict[str, deque] = {}
        self._latest: Dict[str, ResourceSnapshot] = {}

        # Alert thresholds
        self._cpu_warn_pct: float = 80.0
        self._cpu_crit_pct: float = 95.0
        self._memory_warn_pct: float = 85.0
        self._memory_crit_pct: float = 95.0

        self._alerts: List[Dict[str, Any]] = []
        self._monitor_task: Optional[asyncio.Task] = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        self._running = True
        self._monitor_task = asyncio.create_task(self._poll_loop())
        logger.info("ResourceMonitor: started (poll=%dms)", self._poll_interval_ms)

    async def stop(self) -> None:
        self._running = False
        if self._monitor_task and not self._monitor_task.done():
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        logger.info("ResourceMonitor: stopped")

    # ------------------------------------------------------------------
    # Polling
    # ------------------------------------------------------------------

    async def _poll_loop(self) -> None:
        while self._running:
            try:
                await self._sample()
                self._check_thresholds()
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("ResourceMonitor: poll error")
            await asyncio.sleep(self._poll_interval_ms / 1000.0)

    async def _sample(self) -> None:
        """Sample current resource usage. In production, reads from node agents."""
        # Placeholder — real impl reads from node agents / cAdvisor / Prometheus
        pass

    def _check_thresholds(self) -> None:
        with self._lock:
            for node_id, snap in self._latest.items():
                if snap.cpu_pct > self._cpu_crit_pct:
                    self._add_alert("critical", node_id, "cpu", snap.cpu_pct)
                elif snap.cpu_pct > self._cpu_warn_pct:
                    self._add_alert("warning", node_id, "cpu", snap.cpu_pct)
                if snap.memory_pct > self._memory_crit_pct:
                    self._add_alert("critical", node_id, "memory", snap.memory_pct)
                elif snap.memory_pct > self._memory_warn_pct:
                    self._add_alert("warning", node_id, "memory", snap.memory_pct)

    # ------------------------------------------------------------------
    # Data ingestion
    # ------------------------------------------------------------------

    def record_snapshot(self, snap: ResourceSnapshot) -> None:
        with self._lock:
            if snap.node_id not in self._history:
                self._history[snap.node_id] = deque(maxlen=self._max_history)
            self._history[snap.node_id].append(snap)
            self._latest[snap.node_id] = snap

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_latest(self, node_id: str) -> Optional[ResourceSnapshot]:
        with self._lock:
            return self._latest.get(node_id)

    def get_history(self, node_id: str) -> List[ResourceSnapshot]:
        with self._lock:
            q = self._history.get(node_id)
            return list(q) if q else []

    def get_node_stats(self, node_id: str) -> Dict[str, Any]:
        """Aggregated stats for a node."""
        history = self.get_history(node_id)
        if not history:
            return {"node_id": node_id, "samples": 0}

        cpus = [s.cpu_pct for s in history]
        mems = [s.memory_pct for s in history]
        return {
            "node_id": node_id,
            "samples": len(history),
            "cpu_avg": sum(cpus) / len(cpus),
            "cpu_max": max(cpus),
            "memory_avg": sum(mems) / len(mems),
            "memory_max": max(mems),
            "latest": self._latest.get(node_id),
        }

    def get_alerts(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._lock:
            return self._alerts[-limit:]

    def clear_alerts(self) -> None:
        with self._lock:
            self._alerts.clear()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _add_alert(self, level: str, node_id: str, resource: str, value: float) -> None:
        alert = {
            "level": level,
            "node_id": node_id,
            "resource": resource,
            "value": value,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._alerts.append(alert)
        if len(self._alerts) > 1000:
            self._alerts = self._alerts[-1000:]

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def health_report(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "nodes_monitored": len(self._history),
                "samples_collected": sum(len(h) for h in self._history.values()),
                "alerts_pending": len(self._alerts),
                "latest_alerts": self._alerts[-5:],
            }
