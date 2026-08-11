"""
Heartbeat Monitor — Monitors connection liveness via periodic heartbeats
with timeout detection, automatic recovery triggers, and status tracking.

Heartbeat → Timeout → Reconnect → Recovery
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class HeartbeatStatus(str, Enum):
    ALIVE = "alive"
    LATE = "late"
    MISSING = "missing"
    DEAD = "dead"


@dataclass
class HeartbeatRecord:
    connection_id: str
    exchange_id: str
    status: HeartbeatStatus = HeartbeatStatus.ALIVE
    last_heartbeat: Optional[datetime] = None
    last_sent: Optional[datetime] = None
    missed_count: int = 0
    total_heartbeats: int = 0
    avg_latency_ms: float = 0.0
    max_latency_ms: float = 0.0


class HeartbeatMonitor:
    """
    Monitors connection liveness through periodic heartbeat signals.

    Detects late/missing heartbeats, triggers reconnection when
    a connection is considered dead, and tracks heartbeat statistics.

    Usage::

        monitor = HeartbeatMonitor()
        await monitor.initialize()
        await monitor.register("conn_001", "binance")
        await monitor.start()
        await monitor.record_heartbeat("conn_001")
    """

    def __init__(
        self,
        heartbeat_interval: float = 5.0,
        heartbeat_timeout: float = 15.0,
        max_missed_heartbeats: int = 3,
    ) -> None:
        self.heartbeat_interval = heartbeat_interval
        self.heartbeat_timeout = heartbeat_timeout
        self.max_missed_heartbeats = max_missed_heartbeats
        self._records: dict[str, HeartbeatRecord] = {}
        self._on_timeout_callbacks: list[Callable] = []
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._monitor_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        """Initialize the heartbeat monitor."""
        logger.info("HeartbeatMonitor initialized.")

    async def start(self) -> None:
        """Start heartbeat sending and monitoring."""
        self._heartbeat_task = asyncio.create_task(self._send_heartbeats())
        self._monitor_task = asyncio.create_task(self._monitor_heartbeats())
        logger.info("HeartbeatMonitor started.")

    async def stop(self) -> None:
        """Stop heartbeat monitoring."""
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
        if self._monitor_task:
            self._monitor_task.cancel()
        logger.info("HeartbeatMonitor stopped.")

    def on_timeout(self, callback: Callable) -> None:
        """Register a callback for heartbeat timeout events."""
        self._on_timeout_callbacks.append(callback)

    # ---- Registration ----

    async def register(self, connection_id: str, exchange_id: str) -> None:
        """Register a connection for heartbeat monitoring."""
        async with self._lock:
            self._records[connection_id] = HeartbeatRecord(
                connection_id=connection_id,
                exchange_id=exchange_id,
            )
        logger.debug("Registered heartbeat monitor for: %s", connection_id)

    async def unregister(self, connection_id: str) -> bool:
        """Remove a connection from heartbeat monitoring."""
        async with self._lock:
            return self._records.pop(connection_id, None) is not None

    # ---- Heartbeat Operations ----

    async def record_heartbeat(
        self, connection_id: str, latency_ms: float = 0.0
    ) -> None:
        """Record a received heartbeat."""
        record = self._records.get(connection_id)
        if record is None:
            return

        async with self._lock:
            record.last_heartbeat = datetime.now(timezone.utc)
            record.status = HeartbeatStatus.ALIVE
            record.missed_count = 0
            record.total_heartbeats += 1
            if record.total_heartbeats == 1:
                record.avg_latency_ms = latency_ms
            else:
                record.avg_latency_ms = (
                    record.avg_latency_ms * 0.9 + latency_ms * 0.1
                )
            record.max_latency_ms = max(record.max_latency_ms, latency_ms)

    async def send_heartbeat(self, connection_id: str) -> None:
        """Send a heartbeat signal to a connection."""
        record = self._records.get(connection_id)
        if record is None:
            return
        record.last_sent = datetime.now(timezone.utc)
        # Placeholder: actual heartbeat send over transport

    async def get_status(self, connection_id: str) -> Optional[HeartbeatStatus]:
        """Get the heartbeat status for a connection."""
        record = self._records.get(connection_id)
        return record.status if record else None

    async def get_record(self, connection_id: str) -> Optional[HeartbeatRecord]:
        """Get the full heartbeat record for a connection."""
        return self._records.get(connection_id)

    async def get_summary(self) -> dict[str, Any]:
        """Get heartbeat summary for all connections."""
        total = len(self._records)
        alive = sum(1 for r in self._records.values() if r.status == HeartbeatStatus.ALIVE)
        late = sum(1 for r in self._records.values() if r.status == HeartbeatStatus.LATE)
        missing = sum(1 for r in self._records.values() if r.status == HeartbeatStatus.MISSING)
        dead = sum(1 for r in self._records.values() if r.status == HeartbeatStatus.DEAD)

        return {
            "total": total,
            "alive": alive,
            "late": late,
            "missing": missing,
            "dead": dead,
        }

    # ---- Background Tasks ----

    async def _send_heartbeats(self) -> None:
        """Periodically send heartbeats to all registered connections."""
        while True:
            try:
                await asyncio.sleep(self.heartbeat_interval)
                for conn_id in list(self._records.keys()):
                    await self.send_heartbeat(conn_id)
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Heartbeat send error")

    async def _monitor_heartbeats(self) -> None:
        """Monitor heartbeat responses and detect timeouts."""
        while True:
            try:
                await asyncio.sleep(self.heartbeat_interval)
                now = datetime.now(timezone.utc)
                for conn_id, record in list(self._records.items()):
                    if record.last_heartbeat is None:
                        continue

                    elapsed = (now - record.last_heartbeat).total_seconds()

                    if elapsed > self.heartbeat_timeout * self.max_missed_heartbeats:
                        if record.status != HeartbeatStatus.DEAD:
                            record.status = HeartbeatStatus.DEAD
                            record.missed_count = self.max_missed_heartbeats + 1
                            logger.warning("Heartbeat DEAD for %s", conn_id)
                            await self._trigger_timeout(conn_id, record)
                    elif elapsed > self.heartbeat_timeout * 2:
                        record.status = HeartbeatStatus.MISSING
                        record.missed_count += 1
                    elif elapsed > self.heartbeat_timeout:
                        record.status = HeartbeatStatus.LATE
                    else:
                        record.status = HeartbeatStatus.ALIVE

            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Heartbeat monitor error")

    async def _trigger_timeout(
        self, connection_id: str, record: HeartbeatRecord
    ) -> None:
        """Trigger timeout callbacks for a dead connection."""
        event = {
            "type": "heartbeat_timeout",
            "connection_id": connection_id,
            "exchange_id": record.exchange_id,
            "missed_count": record.missed_count,
            "last_heartbeat": record.last_heartbeat.isoformat() if record.last_heartbeat else None,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        for callback in self._on_timeout_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(event)
                else:
                    callback(event)
            except Exception:
                logger.exception("Heartbeat timeout callback error")
