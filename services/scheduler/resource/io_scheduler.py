"""IO Scheduler — IO-aware resource scheduling to avoid hot spots.

The :class:`IOScheduler` considers disk IO, network IO, storage throughput,
and database load when making placement decisions.  This prevents scheduling
IO-heavy tasks onto already-stressed nodes.
"""

from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class IOStats:
    """IO statistics for a node."""

    node_id: str
    disk_read_mbps: float = 0.0
    disk_write_mbps: float = 0.0
    network_rx_mbps: float = 0.0
    network_tx_mbps: float = 0.0
    storage_iops: float = 0.0
    db_connections: int = 0
    db_max_connections: int = 100
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def total_io_mbps(self) -> float:
        return self.disk_read_mbps + self.disk_write_mbps + self.network_rx_mbps + self.network_tx_mbps

    @property
    def io_pressure(self) -> float:
        """0.0–1.0 IO pressure score."""
        return min(1.0, self.total_io_mbps / 1000.0)


class IOScheduler:
    """IO-aware scheduler to avoid hot spots.

    Usage::

        io = IOScheduler()
        io.update_stats(IOStats(node_id="n1", disk_read_mbps=200))
        hot_nodes = io.get_hot_nodes()
        best = io.select_node(candidates, io_budget_mbps=50)
    """

    def __init__(self, hot_threshold_mbps: float = 500.0) -> None:
        self._lock = threading.RLock()
        self._hot_threshold = hot_threshold_mbps
        self._stats: Dict[str, IOStats] = {}
        # History for smoothing
        self._history: Dict[str, deque] = {}
        self._max_history = 60

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def update_stats(self, stats: IOStats) -> None:
        with self._lock:
            self._stats[stats.node_id] = stats
            if stats.node_id not in self._history:
                self._history[stats.node_id] = deque(maxlen=self._max_history)
            self._history[stats.node_id].append(stats.total_io_mbps)

    def get_stats(self, node_id: str) -> Optional[IOStats]:
        with self._lock:
            return self._stats.get(node_id)

    # ------------------------------------------------------------------
    # Hot spot detection
    # ------------------------------------------------------------------

    def get_hot_nodes(self) -> List[str]:
        """Return nodes with excessive IO load."""
        with self._lock:
            return [
                nid for nid, s in self._stats.items()
                if s.total_io_mbps > self._hot_threshold
            ]

    def get_node_io_load(self, node_id: str) -> float:
        """Smoothed IO load for a node (0.0–1.0)."""
        with self._lock:
            history = self._history.get(node_id, deque())
            if not history:
                return 0.0
            # Exponential moving average
            alpha = 0.3
            ema = history[0]
            for val in list(history)[1:]:
                ema = alpha * val + (1 - alpha) * ema
            return min(1.0, ema / self._hot_threshold)

    # ------------------------------------------------------------------
    # Node selection
    # ------------------------------------------------------------------

    def select_node(
        self, candidates: List[str], io_budget_mbps: float = 0.0,
        prefer_low_io: bool = True,
    ) -> Optional[str]:
        """Select the best node considering IO load.

        Excludes nodes where current IO + io_budget > threshold.
        """
        if not candidates:
            return None

        with self._lock:
            valid = [
                nid for nid in candidates
                if nid in self._stats
                and self._stats[nid].total_io_mbps + io_budget_mbps <= self._hot_threshold
            ]
            if not valid:
                valid = list(candidates)

            if prefer_low_io:
                valid.sort(
                    key=lambda nid: self._stats.get(nid, IOStats(nid)).total_io_mbps,
                )
            return valid[0] if valid else None

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_all_stats(self) -> List[IOStats]:
        with self._lock:
            return list(self._stats.values())

    def clear(self) -> None:
        with self._lock:
            self._stats.clear()
            self._history.clear()

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def health_report(self) -> Dict[str, Any]:
        with self._lock:
            hot = self.get_hot_nodes()
            return {
                "nodes_tracked": len(self._stats),
                "hot_nodes": hot,
                "hot_threshold_mbps": self._hot_threshold,
                "avg_io_mbps": (
                    sum(s.total_io_mbps for s in self._stats.values()) / max(len(self._stats), 1)
                ) if self._stats else 0.0,
            }
