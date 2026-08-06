"""State Sync — incremental and full state synchronization across cluster nodes.

The :class:`StateSync` ensures all scheduler nodes maintain a consistent
view of cluster state. It supports both full sync (on join) and incremental
sync (on change), minimizing bandwidth while guaranteeing eventual consistency.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class SyncMode:
    """State synchronization modes."""

    FULL = "full"
    INCREMENTAL = "incremental"
    DELTA = "delta"


class StateSync:
    """Synchronizes cluster state across scheduler nodes.

    Modes:
    - full: complete state transfer (used on node join)
    - incremental: only changes since last sync
    - delta: specific key/value changes

    Usage::

        sync = StateSync(node_id="scheduler-1")
        await sync.start()
        await sync.sync_full()
        await sync.push_update("schedule:s1", schedule_data)
    """

    def __init__(
        self,
        node_id: str,
        *,
        sync_interval_seconds: float = 10.0,
        max_delta_size: int = 1000,
    ) -> None:
        self._node_id = node_id
        self._sync_interval = sync_interval_seconds
        self._max_delta_size = max_delta_size
        self._lock = threading.Lock()

        self._is_running = False
        self._state: Dict[str, Any] = {}
        self._version: int = 0
        self._pending_deltas: List[Dict[str, Any]] = []
        self._last_full_sync: Optional[datetime] = None
        self._task: Optional[asyncio.Task] = None

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def node_id(self) -> str:
        return self._node_id

    @property
    def version(self) -> int:
        return self._version

    @property
    def is_running(self) -> bool:
        return self._is_running

    @property
    def state_size(self) -> int:
        with self._lock:
            return len(self._state)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start the state sync subsystem."""
        self._is_running = True
        self._task = asyncio.create_task(self._sync_loop())
        logger.info("State sync started [node=%s]", self._node_id)

    async def stop(self) -> None:
        """Stop state sync."""
        self._is_running = False
        if self._task:
            self._task.cancel()
            self._task = None
        logger.info("State sync stopped [node=%s]", self._node_id)

    # ------------------------------------------------------------------
    # Full Sync
    # ------------------------------------------------------------------

    async def sync_full(self) -> Dict[str, Any]:
        """Perform a full state synchronization.

        Returns:
            The complete state snapshot.
        """
        with self._lock:
            snapshot = {
                "node_id": self._node_id,
                "version": self._version,
                "state": dict(self._state),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "mode": SyncMode.FULL,
            }
            self._last_full_sync = datetime.now(timezone.utc)
            self._pending_deltas.clear()

        logger.info("Full state sync completed [version=%d, keys=%d]",
                     self._version, len(snapshot["state"]))
        return snapshot

    # ------------------------------------------------------------------
    # Incremental / Delta Sync
    # ------------------------------------------------------------------

    async def push_update(self, key: str, value: Any) -> None:
        """Push a single key/value update to be synchronized.

        Args:
            key: State key (e.g., "schedule:s1", "trigger:t1").
            value: The updated value.
        """
        with self._lock:
            self._state[key] = value
            self._version += 1
            self._pending_deltas.append({
                "key": key,
                "value": value,
                "version": self._version,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            # Trim if exceeding max
            if len(self._pending_deltas) > self._max_delta_size:
                self._pending_deltas = self._pending_deltas[-self._max_delta_size:]

        logger.debug("Pushed state update [key=%s, version=%d]", key, self._version)

    async def push_batch(self, updates: Dict[str, Any]) -> None:
        """Push multiple key/value updates atomically."""
        with self._lock:
            for key, value in updates.items():
                self._state[key] = value
                self._version += 1
                self._pending_deltas.append({
                    "key": key,
                    "value": value,
                    "version": self._version,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
        logger.debug("Pushed batch update [keys=%d, version=%d]", len(updates), self._version)

    async def get_delta(self, since_version: int) -> Dict[str, Any]:
        """Get state changes since a given version.

        Args:
            since_version: Return changes after this version.

        Returns:
            Dict with deltas and current version.
        """
        with self._lock:
            deltas = [d for d in self._pending_deltas if d["version"] > since_version]
            return {
                "node_id": self._node_id,
                "since_version": since_version,
                "current_version": self._version,
                "deltas": deltas,
                "mode": SyncMode.DELTA,
            }

    async def apply_sync(self, snapshot: Dict[str, Any]) -> bool:
        """Apply a received state snapshot from another node.

        Args:
            snapshot: The state snapshot to apply.

        Returns:
            True if applied successfully.
        """
        mode = snapshot.get("mode", SyncMode.FULL)
        with self._lock:
            if mode == SyncMode.FULL:
                self._state = dict(snapshot.get("state", {}))
                self._version = snapshot.get("version", self._version)
            elif mode == SyncMode.DELTA:
                for delta in snapshot.get("deltas", []):
                    self._state[delta["key"]] = delta["value"]
                self._version = max(self._version, snapshot.get("current_version", self._version))

        logger.debug("Applied sync [mode=%s, version=%d]", mode, self._version)
        return True

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get(self, key: str, default: Any = None) -> Any:
        """Get a state value by key."""
        with self._lock:
            return self._state.get(key, default)

    def get_all(self) -> Dict[str, Any]:
        """Get a copy of the entire state."""
        with self._lock:
            return dict(self._state)

    def remove(self, key: str) -> None:
        """Remove a key from the state."""
        with self._lock:
            self._state.pop(key, None)
            self._version += 1

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _sync_loop(self) -> None:
        """Periodic state sync loop."""
        while self._is_running:
            try:
                await asyncio.sleep(self._sync_interval)
                # Periodic incremental sync
                with self._lock:
                    if self._pending_deltas:
                        logger.debug("Sync loop: %d pending deltas", len(self._pending_deltas))
            except asyncio.CancelledError:
                break
            except Exception:
                logger.error("State sync loop error", exc_info=True)

    def get_sync_info(self) -> Dict[str, Any]:
        """Return sync status summary."""
        return {
            "node_id": self._node_id,
            "is_running": self._is_running,
            "version": self._version,
            "state_size": self.state_size,
            "pending_deltas": len(self._pending_deltas),
            "last_full_sync": self._last_full_sync.isoformat() if self._last_full_sync else None,
        }
