"""Heartbeat Monitor — monitors node health via periodic heartbeat signals.

Flow::

    Worker → Heartbeat → Coordinator → Health Check

When a heartbeat is lost:

    Heartbeat Lost → Failover Trigger
"""

from __future__ import annotations

import asyncio
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class HeartbeatRecord:
    """A record of heartbeats from a cluster node."""

    node_id: str
    last_heartbeat: datetime = field(default_factory=datetime.utcnow)
    missed_count: int = 0
    total_received: int = 0
    is_alive: bool = True
    latency_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def record_beat(self, *, latency_ms: float = 0.0) -> None:
        self.last_heartbeat = datetime.utcnow()
        self.total_received += 1
        self.missed_count = 0
        self.is_alive = True
        self.latency_ms = latency_ms

    def record_miss(self) -> None:
        self.missed_count += 1

    def mark_dead(self) -> None:
        self.is_alive = False


class HeartbeatMonitor:
    """Monitors heartbeats from cluster nodes and detects failures.

    Usage::

        monitor = HeartbeatMonitor(interval_seconds=5.0, timeout_seconds=15.0)
        await monitor.start()
        monitor.record_heartbeat("node_abc")
    """

    def __init__(
        self,
        *,
        interval_seconds: float = 5.0,
        timeout_seconds: float = 15.0,
        max_missed_beats: int = 3,
    ) -> None:
        self._interval = interval_seconds
        self._timeout = timeout_seconds
        self._max_missed_beats = max_missed_beats
        self._lock = threading.RLock()
        self._records: Dict[str, HeartbeatRecord] = {}

        self._started = False
        self._check_task: Optional[asyncio.Task] = None

        # Callbacks
        self._on_timeout_callbacks: List[Callable[[str], Any]] = []
        self._on_recovery_callbacks: List[Callable[[str], Any]] = []

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def monitored_count(self) -> int:
        with self._lock:
            return len(self._records)

    @property
    def alive_count(self) -> int:
        with self._lock:
            return sum(1 for r in self._records.values() if r.is_alive)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start the heartbeat monitor."""
        self._started = True
        self._check_task = asyncio.create_task(self._check_loop())
        logger.info("HeartbeatMonitor: started (interval=%.1fs, timeout=%.1fs)",
                     self._interval, self._timeout)

    async def stop(self) -> None:
        """Stop the heartbeat monitor."""
        self._started = False
        if self._check_task:
            self._check_task.cancel()
            try:
                await self._check_task
            except asyncio.CancelledError:
                pass
        logger.info("HeartbeatMonitor: stopped")

    # ------------------------------------------------------------------
    # Heartbeat recording
    # ------------------------------------------------------------------

    def record_heartbeat(
        self,
        node_id: str,
        *,
        latency_ms: float = 0.0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record a heartbeat from a node."""
        with self._lock:
            if node_id not in self._records:
                self._records[node_id] = HeartbeatRecord(node_id=node_id)
            record = self._records[node_id]
            was_dead = not record.is_alive
            record.record_beat(latency_ms=latency_ms)
            if metadata:
                record.metadata.update(metadata)

        if was_dead:
            logger.info("HeartbeatMonitor: node %s recovered", node_id)
            for cb in self._on_recovery_callbacks:
                try:
                    cb(node_id)
                except Exception:
                    logger.exception("HeartbeatMonitor: recovery callback error")

    def get_record(self, node_id: str) -> Optional[HeartbeatRecord]:
        """Get the heartbeat record for a node."""
        with self._lock:
            return self._records.get(node_id)

    async def list_records(self) -> List[HeartbeatRecord]:
        """List all heartbeat records."""
        with self._lock:
            return list(self._records.values())

    async def remove_node(self, node_id: str) -> None:
        """Remove a node from heartbeat monitoring."""
        with self._lock:
            self._records.pop(node_id, None)

    # ------------------------------------------------------------------
    # Monitoring loop
    # ------------------------------------------------------------------

    async def _check_loop(self) -> None:
        """Periodically check for nodes that have missed heartbeats."""
        while self._started:
            try:
                await asyncio.sleep(self._interval)
                now = datetime.utcnow()

                with self._lock:
                    for node_id, record in list(self._records.items()):
                        elapsed = (now - record.last_heartbeat).total_seconds()
                        if elapsed > self._timeout:
                            record.record_miss()
                            if record.missed_count >= self._max_missed_beats and record.is_alive:
                                record.mark_dead()
                                logger.warning("HeartbeatMonitor: node %s timed out (missed %d beats)",
                                               node_id, record.missed_count)
                                for cb in self._on_timeout_callbacks:
                                    try:
                                        cb(node_id)
                                    except Exception:
                                        logger.exception("HeartbeatMonitor: timeout callback error")
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("HeartbeatMonitor: error in check loop")

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    def on_timeout(self, callback: Callable[[str], Any]) -> None:
        """Register a callback for heartbeat timeout events."""
        self._on_timeout_callbacks.append(callback)

    def on_recovery(self, callback: Callable[[str], Any]) -> None:
        """Register a callback for node recovery events."""
        self._on_recovery_callbacks.append(callback)

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def health_report(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "monitored_nodes": self.monitored_count,
                "alive_nodes": self.alive_count,
                "interval_seconds": self._interval,
                "timeout_seconds": self._timeout,
                "nodes": {
                    node_id: {
                        "alive": record.is_alive,
                        "missed": record.missed_count,
                        "total": record.total_received,
                        "latency_ms": record.latency_ms,
                    }
                    for node_id, record in self._records.items()
                },
            }
