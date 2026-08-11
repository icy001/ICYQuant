"""
Signal Snapshot — Runtime state capture for signal recovery.

Part of Commit 13 Part 1.2: Signal & Alpha Engine.

Captures:
    - Active signals in cache
    - Signal registry state
    - Recent expiration history
    - Generator state

Used for recovery after restarts or failures.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from services.strategy.signal.signal_engine import Signal
from services.strategy.signal.signal_cache import SignalCache

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

@dataclass
class SignalSnapshot:
    """A point-in-time capture of the signal subsystem state."""
    snapshot_id: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    checksum: str = ""

    # Signal state
    active_signals: List[Dict[str, Any]] = field(default_factory=list)
    active_signal_ids: List[str] = field(default_factory=list)
    signal_count: int = 0

    # Metadata
    version: str = "1.0"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def compute_checksum(self) -> str:
        """Compute SHA256 checksum of the active signal data."""
        raw = json.dumps(self.active_signals, sort_keys=True, default=str)
        self.checksum = hashlib.sha256(raw.encode()).hexdigest()
        return self.checksum

    def to_dict(self) -> Dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "created_at": self.created_at.isoformat(),
            "checksum": self.checksum,
            "signal_count": self.signal_count,
            "active_signal_ids": self.active_signal_ids,
            "version": self.version,
            "metadata": self.metadata,
        }


@dataclass
class SnapshotConfig:
    """Configuration for signal snapshotting."""
    max_snapshots: int = 100
    auto_snapshot_interval_seconds: float = 60.0
    retain_min_snapshots: int = 5


# ---------------------------------------------------------------------------
# Signal Snapshot
# ---------------------------------------------------------------------------

class SignalSnapshot:
    """Manages signal subsystem snapshots for state recovery."""

    def __init__(self, cache: SignalCache, config: Optional[SnapshotConfig] = None):
        self.cache = cache
        self.config = config or SnapshotConfig()
        self._snapshots: List[SignalSnapshot] = []

    # ------------------------------------------------------------------
    # Snapshot Operations
    # ------------------------------------------------------------------

    async def capture(self, metadata: Optional[Dict[str, Any]] = None) -> SignalSnapshot:
        """Capture the current state of the signal subsystem."""
        active_signals = await self.cache.get_active()

        snapshot = SignalSnapshot(
            snapshot_id=f"snap_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')}",
            active_signals=[s.to_dict() for s in active_signals],
            active_signal_ids=[s.signal_id for s in active_signals],
            signal_count=len(active_signals),
            metadata=metadata or {},
        )
        snapshot.compute_checksum()

        self._snapshots.append(snapshot)

        # Enforce max snapshots
        while len(self._snapshots) > self.config.max_snapshots:
            removed = self._snapshots.pop(0)
            logger.debug("Pruned old snapshot: %s", removed.snapshot_id)

        logger.info("Captured signal snapshot %s: %d active signals (checksum=%s)",
                     snapshot.snapshot_id, snapshot.signal_count, snapshot.checksum[:8])
        return snapshot

    async def restore(self, snapshot_id: Optional[str] = None) -> Optional[SignalSnapshot]:
        """Restore signal state from a snapshot.

        Args:
            snapshot_id: Specific snapshot to restore, or the latest if None.

        Returns:
            The restored snapshot, or None if no snapshot found.
        """
        if snapshot_id:
            snapshot = self.get_snapshot(snapshot_id)
        else:
            snapshot = self.latest_snapshot

        if not snapshot:
            logger.warning("No snapshot found for restore")
            return None

        # Validate checksum
        original_checksum = snapshot.checksum
        snapshot.compute_checksum()
        if snapshot.checksum != original_checksum:
            logger.error("Snapshot %s checksum mismatch — data may be corrupted", snapshot.snapshot_id)

        # Restore active signals to cache
        restored_count = 0
        for sig_dict in snapshot.active_signals:
            try:
                signal = Signal(
                    signal_id=sig_dict.get("signal_id", ""),
                    strategy_id=sig_dict.get("strategy_id", ""),
                    instrument=sig_dict.get("instrument", ""),
                    confidence=sig_dict.get("confidence", 0.0),
                    reason=sig_dict.get("reason", ""),
                    alpha_scores=sig_dict.get("alpha_scores", {}),
                    factor_contributions=sig_dict.get("factor_contributions", {}),
                    tags=sig_dict.get("tags", []),
                    metadata=sig_dict.get("metadata", {}),
                )
                self.cache.put(signal)
                restored_count += 1
            except Exception:
                logger.exception("Failed to restore signal from snapshot")

        logger.info("Restored %d signals from snapshot %s", restored_count, snapshot.snapshot_id)
        return snapshot

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_snapshot(self, snapshot_id: str) -> Optional[SignalSnapshot]:
        for snap in self._snapshots:
            if snap.snapshot_id == snapshot_id:
                return snap
        return None

    @property
    def latest_snapshot(self) -> Optional[SignalSnapshot]:
        return self._snapshots[-1] if self._snapshots else None

    def list_snapshots(self, limit: int = 20) -> List[Dict[str, Any]]:
        return [s.to_dict() for s in self._snapshots[-limit:]]

    @property
    def snapshot_count(self) -> int:
        return len(self._snapshots)

    def clear(self) -> None:
        self._snapshots.clear()
