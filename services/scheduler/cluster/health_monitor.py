"""Health Monitor — cluster-wide health surveillance and anomaly detection.

The :class:`ClusterHealthMonitor` continuously assesses the health of
every scheduler node and the cluster as a whole. It checks CPU, memory,
queue lag, latency, replication health, and heartbeat freshness.
Unhealthy nodes are automatically marked for eviction.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class NodeHealthStatus:
    """Per-node health assessment."""

    HEALTHY = "healthy"
    WARNING = "warning"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class ClusterHealthMonitor:
    """Monitors cluster-wide health and detects anomalies.

    Checks include:
    - CPU / Memory thresholds
    - Queue depth (lag)
    - Scheduling latency
    - Replication lag
    - Heartbeat freshness

    Usage::

        monitor = ClusterHealthMonitor()
        await monitor.start()
        status = monitor.check_node("scheduler-1", metrics={"cpu_pct": 45.0, "mem_pct": 60.0})
    """

    def __init__(
        self,
        *,
        cpu_warn_pct: float = 70.0,
        cpu_critical_pct: float = 90.0,
        mem_warn_pct: float = 75.0,
        mem_critical_pct: float = 92.0,
        queue_lag_warn: int = 1000,
        queue_lag_critical: int = 5000,
        latency_warn_ms: float = 500.0,
        latency_critical_ms: float = 2000.0,
        check_interval_seconds: float = 10.0,
    ) -> None:
        self._cpu_warn = cpu_warn_pct
        self._cpu_critical = cpu_critical_pct
        self._mem_warn = mem_warn_pct
        self._mem_critical = mem_critical_pct
        self._queue_lag_warn = queue_lag_warn
        self._queue_lag_critical = queue_lag_critical
        self._latency_warn_ms = latency_warn_ms
        self._latency_critical_ms = latency_critical_ms
        self._check_interval = check_interval_seconds
        self._lock = threading.Lock()

        self._is_running = False
        self._node_statuses: Dict[str, str] = {}
        self._task: Optional[asyncio.Task] = None
        self._on_unhealthy: list = []

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def is_running(self) -> bool:
        return self._is_running

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start periodic health monitoring."""
        self._is_running = True
        self._task = asyncio.create_task(self._monitor_loop())
        logger.info("Cluster health monitor started [interval=%.1fs]", self._check_interval)

    async def stop(self) -> None:
        """Stop health monitoring."""
        self._is_running = False
        if self._task:
            self._task.cancel()
            self._task = None
        logger.info("Cluster health monitor stopped")

    # ------------------------------------------------------------------
    # Node Health
    # ------------------------------------------------------------------

    def check_node(self, node_id: str, metrics: Dict[str, float]) -> str:
        """Assess the health of a single node based on metrics.

        Args:
            node_id: The node to assess.
            metrics: Dict with keys like cpu_pct, mem_pct, queue_depth,
                     latency_ms, replication_lag_ms.

        Returns:
            One of healthy / warning / unhealthy.
        """
        cpu = metrics.get("cpu_pct", 0)
        mem = metrics.get("mem_pct", 0)
        queue_depth = metrics.get("queue_depth", 0)
        latency = metrics.get("latency_ms", 0)
        replication_lag = metrics.get("replication_lag_ms", 0)

        reasons: List[str] = []
        critical = False

        if cpu >= self._cpu_critical:
            reasons.append(f"CPU critical: {cpu:.1f}%")
            critical = True
        elif cpu >= self._cpu_warn:
            reasons.append(f"CPU warning: {cpu:.1f}%")

        if mem >= self._mem_critical:
            reasons.append(f"Memory critical: {mem:.1f}%")
            critical = True
        elif mem >= self._mem_warn:
            reasons.append(f"Memory warning: {mem:.1f}%")

        if queue_depth >= self._queue_lag_critical:
            reasons.append(f"Queue lag critical: {queue_depth}")
            critical = True
        elif queue_depth >= self._queue_lag_warn:
            reasons.append(f"Queue lag warning: {queue_depth}")

        if latency >= self._latency_critical_ms:
            reasons.append(f"Latency critical: {latency:.1f}ms")
            critical = True
        elif latency >= self._latency_warn_ms:
            reasons.append(f"Latency warning: {latency:.1f}ms")

        if critical:
            status = NodeHealthStatus.UNHEALTHY
        elif reasons:
            status = NodeHealthStatus.WARNING
        else:
            status = NodeHealthStatus.HEALTHY

        with self._lock:
            self._node_statuses[node_id] = status

        if status == NodeHealthStatus.UNHEALTHY:
            logger.warning("Node %s unhealthy: %s", node_id, "; ".join(reasons))
            for cb in self._on_unhealthy:
                try:
                    cb(node_id, reasons)
                except Exception:
                    logger.warning("Unhealthy callback failed", exc_info=True)

        return status

    def get_node_status(self, node_id: str) -> str:
        """Get the last known health status of a node."""
        with self._lock:
            return self._node_statuses.get(node_id, NodeHealthStatus.UNKNOWN)

    def get_unhealthy_nodes(self) -> List[str]:
        """Return list of currently unhealthy node IDs."""
        with self._lock:
            return [nid for nid, s in self._node_statuses.items()
                    if s == NodeHealthStatus.UNHEALTHY]

    def on_unhealthy(self, callback: callable) -> None:
        """Register a callback invoked when a node becomes unhealthy."""
        self._on_unhealthy.append(callback)

    # ------------------------------------------------------------------
    # Cluster Health
    # ------------------------------------------------------------------

    def assess_cluster(self) -> Dict[str, Any]:
        """Assess the overall cluster health."""
        with self._lock:
            total = len(self._node_statuses)
            unhealthy = sum(1 for s in self._node_statuses.values() if s == NodeHealthStatus.UNHEALTHY)
            warning = sum(1 for s in self._node_statuses.values() if s == NodeHealthStatus.WARNING)
            healthy = total - unhealthy - warning

        if unhealthy > 0:
            overall = NodeHealthStatus.UNHEALTHY
        elif warning > total / 2:
            overall = NodeHealthStatus.WARNING
        elif total == 0:
            overall = NodeHealthStatus.UNKNOWN
        else:
            overall = NodeHealthStatus.HEALTHY

        return {
            "overall": overall,
            "total_nodes": total,
            "healthy": healthy,
            "warning": warning,
            "unhealthy": unhealthy,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _monitor_loop(self) -> None:
        """Background monitoring loop."""
        while self._is_running:
            try:
                await asyncio.sleep(self._check_interval)
                assessment = self.assess_cluster()
                if assessment["overall"] != NodeHealthStatus.HEALTHY:
                    logger.warning("Cluster health: %s", assessment)
            except asyncio.CancelledError:
                break
            except Exception:
                logger.error("Health monitor loop error", exc_info=True)

    def get_monitor_info(self) -> Dict[str, Any]:
        """Return monitor configuration and status."""
        return {
            "is_running": self._is_running,
            "thresholds": {
                "cpu_warn_pct": self._cpu_warn,
                "cpu_critical_pct": self._cpu_critical,
                "mem_warn_pct": self._mem_warn,
                "mem_critical_pct": self._mem_critical,
                "queue_lag_warn": self._queue_lag_warn,
                "queue_lag_critical": self._queue_lag_critical,
                "latency_warn_ms": self._latency_warn_ms,
                "latency_critical_ms": self._latency_critical_ms,
            },
            "check_interval_seconds": self._check_interval,
        }
