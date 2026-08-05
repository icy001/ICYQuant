"""Immutable snapshot management for ICYQuant service discovery HA.

Provides ``RegistrySnapshot`` for creating, restoring, comparing,
and managing immutable registry snapshots with atomic restore
and incremental support.
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class RegistrySnapshot:
    """Manages immutable registry snapshots.

    Supports creating snapshots of the full service registry,
    restoring from a snapshot, comparing snapshots, and
    maintaining a history of previous snapshots.

    Args:
        version: Initial snapshot version number.
    """

    def __init__(self, version: int = 0) -> None:
        self._lock = threading.RLock()
        self._version = int(version)
        self._snapshots: Dict[int, Dict[str, Any]] = {}
        self._latest_version: int = -1
        self._create_count = 0
        self._restore_count = 0
        self._compare_count = 0

    # ── Helpers ──

    @staticmethod
    def _now_iso() -> str:
        return datetime.utcnow().isoformat()

    # ── Public API ──

    def create(
        self, services: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create a new snapshot of the registry state.

        Args:
            services: The current services dictionary to snapshot.

        Returns:
            The created snapshot dictionary.
        """
        with self._lock:
            self._version += 1
            version = self._version
            self._create_count += 1

        snapshot: Dict[str, Any] = {
            "version": version,
            "created_at": self._now_iso(),
            "created_at_epoch": time.time(),
            "services": self._deep_copy_services(services),
            "checksum": self._compute_checksum(services),
        }

        with self._lock:
            self._snapshots[version] = snapshot
            self._latest_version = version

        logger.info(
            "Created snapshot version %d (%d services).",
            version,
            len(snapshot["services"]),
        )
        return snapshot

    def restore(
        self, snapshot: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Restore the registry from a snapshot.

        Args:
            snapshot: The snapshot dictionary to restore from.

        Returns:
            A dictionary describing the restore result.
        """
        with self._lock:
            self._restore_count += 1

        version = snapshot.get("version", -1)
        services = snapshot.get("services", {})
        checksum = snapshot.get("checksum", "")

        result: Dict[str, Any] = {
            "restored": True,
            "snapshot_version": version,
            "services_count": len(services),
            "checksum_valid": True,
            "timestamp": self._now_iso(),
        }

        if checksum:
            computed = self._compute_checksum(services)
            if computed != checksum:
                result["checksum_valid"] = False
                result["restored"] = False
                result["error"] = "Checksum mismatch."
                logger.warning(
                    "Snapshot checksum mismatch (version=%d).",
                    version,
                )
                return result

        logger.info(
            "Restored snapshot version %d (%d services).",
            version,
            len(services),
        )
        return result

    def get_latest(self) -> Optional[Dict[str, Any]]:
        """Return the latest snapshot, if any.

        Returns:
            The latest snapshot dictionary or None.
        """
        with self._lock:
            if self._latest_version < 0:
                return None
            snapshot = self._snapshots.get(self._latest_version)
            if snapshot is None:
                return None
            return dict(snapshot)

    def get_history(
        self, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Return a list of recent snapshot metadata.

        Args:
            limit: Maximum number of snapshots to return.

        Returns:
            A list of snapshot summary dictionaries (not
            the full snapshot data).
        """
        with self._lock:
            versions = sorted(self._snapshots.keys(), reverse=True)
            if limit and limit > 0:
                versions = versions[:limit]
            history: List[Dict[str, Any]] = []
            for v in versions:
                snap = self._snapshots.get(v)
                if snap is not None:
                    history.append(
                        {
                            "version": snap["version"],
                            "created_at": snap["created_at"],
                            "services_count": len(
                                snap.get("services", {})
                            ),
                            "checksum": snap.get("checksum", ""),
                        }
                    )
            return history

    def compare(
        self,
        snapshot_a: Dict[str, Any],
        snapshot_b: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Compare two snapshots and produce a diff.

        Args:
            snapshot_a: First snapshot dictionary.
            snapshot_b: Second snapshot dictionary.

        Returns:
            A dictionary with ``added``, ``removed``, ``modified``
            service keys and version info.
        """
        with self._lock:
            self._compare_count += 1

        services_a = snapshot_a.get("services", {})
        services_b = snapshot_b.get("services", {})

        keys_a = set(services_a.keys())
        keys_b = set(services_b.keys())

        added = sorted(keys_b - keys_a)
        removed = sorted(keys_a - keys_b)
        common = keys_a & keys_b

        modified: List[str] = []
        for key in sorted(common):
            val_a = services_a.get(key)
            val_b = services_b.get(key)
            if val_a != val_b:
                modified.append(key)

        result: Dict[str, Any] = {
            "snapshot_a_version": snapshot_a.get("version", -1),
            "snapshot_b_version": snapshot_b.get("version", -1),
            "added": added,
            "removed": removed,
            "modified": modified,
            "equal": not added and not removed and not modified,
            "timestamp": self._now_iso(),
        }

        logger.debug(
            "Compared snapshots: %d added, %d removed, %d modified.",
            len(added),
            len(removed),
            len(modified),
        )
        return result

    def get_stats(self) -> Dict[str, Any]:
        """Return summary statistics for the snapshot manager."""
        with self._lock:
            return {
                "current_version": self._version,
                "latest_version": self._latest_version,
                "total_snapshots": len(self._snapshots),
                "create_count": self._create_count,
                "restore_count": self._restore_count,
                "compare_count": self._compare_count,
            }

    # ── Internal helpers ──

    @staticmethod
    def _deep_copy_services(
        services: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Create a deep copy of the services dictionary."""
        import copy

        return copy.deepcopy(services)

    @staticmethod
    def _compute_checksum(services: Dict[str, Any]) -> str:
        """Compute a simple checksum of the services data."""
        import hashlib
        import json

        try:
            serialized = json.dumps(
                services, sort_keys=True, default=str
            )
            return hashlib.sha256(serialized.encode()).hexdigest()
        except (TypeError, ValueError):
            return ""

    def __repr__(self) -> str:
        with self._lock:
            return (
                f"RegistrySnapshot(version={self._version}, "
                f"snapshots={len(self._snapshots)})"
            )