"""Heartbeat Manager — periodic health signals from scheduler nodes.

The :class:`HeartbeatManager` sends periodic heartbeat signals from each
scheduler node to the cluster coordinator. Missed heartbeats trigger
suspect status and potential failover.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class HeartbeatStatus:
    """Heartbeat health status."""

    HEALTHY = "healthy"
    LAGGING = "lagging"
    MISSED = "missed"
    TIMEOUT = "timeout"


class HeartbeatManager:
    """Sends periodic heartbeats and tracks peer health.

    Usage::

        hb = HeartbeatManager(node_id="scheduler-1", interval_seconds=3.0)
        await hb.start()
        # heartbeats sent automatically in the background
        await hb.stop()
    """

    def __init__(
        self,
        node_id: str,
        *,
        interval_seconds: float = 3.0,
        timeout_seconds: float = 15.0,
    ) -> None:
        self._node_id = node_id
        self._interval = interval_seconds
        self._timeout = timeout_seconds
        self._lock = threading.Lock()

        self._is_running = False
        self._last_sent: Optional[datetime] = None
        self._sequence: int = 0
        self._missed_count: int = 0

        self._peer_heartbeats: Dict[str, datetime] = {}
        self._task: Optional[asyncio.Task] = None

        # Callbacks
        self._on_peer_timeout: list = []

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def node_id(self) -> str:
        return self._node_id

    @property
    def is_running(self) -> bool:
        return self._is_running

    @property
    def last_sent(self) -> Optional[datetime]:
        return self._last_sent

    @property
    def sequence(self) -> int:
        return self._sequence

    @property
    def missed_count(self) -> int:
        return self._missed_count

    @property
    def status(self) -> str:
        if not self._is_running:
            return HeartbeatStatus.MISSED
        if self._missed_count > 3:
            return HeartbeatStatus.TIMEOUT
        if self._missed_count > 0:
            return HeartbeatStatus.LAGGING
        return HeartbeatStatus.HEALTHY

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start sending periodic heartbeats."""
        self._is_running = True
        self._task = asyncio.create_task(self._heartbeat_loop())
        logger.info("Heartbeat manager started [node=%s, interval=%.1fs]",
                     self._node_id, self._interval)

    async def stop(self) -> None:
        """Stop sending heartbeats."""
        self._is_running = False
        if self._task:
            self._task.cancel()
            self._task = None
        logger.info("Heartbeat manager stopped [node=%s]", self._node_id)

    # ------------------------------------------------------------------
    # Peer Tracking
    # ------------------------------------------------------------------

    def record_peer_heartbeat(self, peer_id: str) -> None:
        """Record a heartbeat received from a peer node."""
        with self._lock:
            self._peer_heartbeats[peer_id] = datetime.now(timezone.utc)

    def get_peer_status(self, peer_id: str) -> str:
        """Get the health status of a peer based on its last heartbeat."""
        with self._lock:
            last = self._peer_heartbeats.get(peer_id)
        if last is None:
            return HeartbeatStatus.MISSED

        elapsed = (datetime.now(timezone.utc) - last).total_seconds()
        if elapsed > self._timeout:
            return HeartbeatStatus.TIMEOUT
        if elapsed > self._interval * 2:
            return HeartbeatStatus.LAGGING
        return HeartbeatStatus.HEALTHY

    def get_expired_peers(self) -> list:
        """Return list of peer IDs whose heartbeats have timed out."""
        expired = []
        now = datetime.now(timezone.utc)
        with self._lock:
            for peer_id, last in self._peer_heartbeats.items():
                if (now - last).total_seconds() > self._timeout:
                    expired.append(peer_id)
        return expired

    def on_peer_timeout(self, callback: callable) -> None:
        """Register a callback invoked when a peer times out."""
        self._on_peer_timeout.append(callback)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _heartbeat_loop(self) -> None:
        """Background coroutine that sends periodic heartbeats."""
        while self._is_running:
            try:
                await asyncio.sleep(self._interval)
                self._send_heartbeat()
                await self._check_peers()
            except asyncio.CancelledError:
                break
            except Exception:
                logger.error("Heartbeat loop error", exc_info=True)

    def _send_heartbeat(self) -> None:
        """Send a single heartbeat signal."""
        with self._lock:
            self._sequence += 1
            self._last_sent = datetime.now(timezone.utc)
        logger.debug("Heartbeat sent [node=%s, seq=%d]", self._node_id, self._sequence)

    async def _check_peers(self) -> None:
        """Check for expired peer heartbeats."""
        expired = self.get_expired_peers()
        for peer_id in expired:
            logger.warning("Peer %s heartbeat timed out", peer_id)
            for cb in self._on_peer_timeout:
                try:
                    cb(peer_id)
                except Exception:
                    logger.warning("Peer-timeout callback failed", exc_info=True)

    def get_heartbeat_info(self) -> Dict[str, Any]:
        """Return heartbeat status summary."""
        with self._lock:
            return {
                "node_id": self._node_id,
                "status": self.status,
                "interval_seconds": self._interval,
                "timeout_seconds": self._timeout,
                "last_sent": self._last_sent.isoformat() if self._last_sent else None,
                "sequence": self._sequence,
                "missed_count": self._missed_count,
                "peer_count": len(self._peer_heartbeats),
            }
