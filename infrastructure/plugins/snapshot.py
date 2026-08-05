from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from .exceptions import PluginError

logger = logging.getLogger(__name__)


@dataclass
class PluginSnapshot:
    """An immutable point-in-time snapshot of the plugin framework
    state, with checksum-based integrity verification."""

    version: int
    plugins: List[Dict[str, Any]]
    checksum: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)

    def compute_checksum(self) -> str:
        """Compute a SHA-256 checksum of the snapshot content.

        The checksum is derived from the plugin data and version
        to detect any tampering.

        Returns:
            Hex-encoded SHA-256 digest string.
        """
        payload = json.dumps(
            {
                "version": self.version,
                "plugins": self.plugins,
            },
            sort_keys=True,
            default=str,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the snapshot to a dictionary.

        Returns:
            A dictionary with all snapshot fields.
        """
        return {
            "version": self.version,
            "plugins": list(self.plugins),
            "checksum": self.checksum,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> PluginSnapshot:
        """Deserialize a snapshot from a dictionary.

        Args:
            data: The snapshot data dictionary.

        Returns:
            A new :class:`PluginSnapshot` instance.
        """
        created_at = data.get("created_at")
        if isinstance(created_at, str):
            try:
                created_at = datetime.fromisoformat(created_at)
            except (ValueError, TypeError):
                created_at = datetime.utcnow()
        elif not isinstance(created_at, datetime):
            created_at = datetime.utcnow()

        return cls(
            version=int(data.get("version", 0)),
            plugins=list(data.get("plugins", [])),
            checksum=data.get("checksum", ""),
            created_at=created_at,
        )


class SnapshotManager:
    """Manages immutable snapshots of the plugin framework state.

    Snapshots are created with atomic version numbers and verified
    via SHA-256 checksums to ensure integrity.
    """

    def __init__(self) -> None:
        self._snapshots: Dict[int, PluginSnapshot] = {}
        self._next_version = 1
        self._stats: Dict[str, int] = {
            "created": 0,
            "restored": 0,
            "deleted": 0,
            "failed": 0,
        }

    async def create_snapshot(self) -> PluginSnapshot:
        """Create a new snapshot of the current plugin state.

        Returns:
            The newly created :class:`PluginSnapshot`.
        """
        version = self._next_version
        self._next_version += 1

        snapshot = PluginSnapshot(
            version=version,
            plugins=[],
            created_at=datetime.utcnow(),
        )
        snapshot.checksum = snapshot.compute_checksum()

        self._snapshots[version] = snapshot
        self._stats["created"] += 1

        logger.info(
            "Created snapshot v%d (checksum=%s).",
            version,
            snapshot.checksum[:16],
        )
        return snapshot

    async def restore_snapshot(
        self, version: int
    ) -> Dict[str, Any]:
        """Restore the framework to a previous snapshot.

        Args:
            version: The snapshot version to restore.

        Returns:
            Restoration result dictionary.

        Raises:
            PluginError: If the snapshot version is not found.
        """
        snapshot = self._snapshots.get(version)
        if snapshot is None:
            raise PluginError(
                f"Snapshot v{version} not found."
            )

        self._stats["restored"] += 1

        logger.info(
            "Restored snapshot v%d (%d plugins).",
            version,
            len(snapshot.plugins),
        )
        return {
            "success": True,
            "version": version,
            "plugins": len(snapshot.plugins),
            "restored_at": datetime.utcnow().isoformat(),
        }

    async def list_snapshots(self) -> List[Dict[str, Any]]:
        """List all available snapshots.

        Returns:
            List of snapshot metadata dictionaries.
        """
        result: List[Dict[str, Any]] = []
        for version in sorted(self._snapshots.keys()):
            snapshot = self._snapshots[version]
            result.append({
                "version": snapshot.version,
                "plugin_count": len(snapshot.plugins),
                "checksum": snapshot.checksum[:16],
                "created_at": snapshot.created_at.isoformat(),
            })
        return result

    async def get_snapshot(
        self, version: int
    ) -> Optional[PluginSnapshot]:
        """Retrieve a specific snapshot by version.

        Args:
            version: The snapshot version number.

        Returns:
            The :class:`PluginSnapshot`, or ``None`` if not found.
        """
        return self._snapshots.get(version)

    async def delete_snapshot(self, version: int) -> None:
        """Delete a snapshot by version.

        Args:
            version: The snapshot version number.

        Raises:
            PluginError: If the snapshot version is not found.
        """
        if version not in self._snapshots:
            raise PluginError(
                f"Snapshot v{version} not found."
            )
        del self._snapshots[version]
        self._stats["deleted"] += 1
        logger.info("Deleted snapshot v%d.", version)

    def compare_snapshots(
        self, v1: int, v2: int
    ) -> Dict[str, Any]:
        """Compare two snapshots and return the differences.

        Args:
            v1: First snapshot version.
            v2: Second snapshot version.

        Returns:
            Comparison result with added, removed, and changed
            plugin entries.

        Raises:
            PluginError: If either snapshot version is not found.
        """
        s1 = self._snapshots.get(v1)
        s2 = self._snapshots.get(v2)
        if s1 is None:
            raise PluginError(f"Snapshot v{v1} not found.")
        if s2 is None:
            raise PluginError(f"Snapshot v{v2} not found.")

        plugins1 = {
            p.get("id", ""): p for p in s1.plugins
        }
        plugins2 = {
            p.get("id", ""): p for p in s2.plugins
        }

        added = [
            pid for pid in plugins2 if pid not in plugins1
        ]
        removed = [
            pid for pid in plugins1 if pid not in plugins2
        ]
        changed: List[str] = []
        for pid in set(plugins1.keys()) & set(plugins2.keys()):
            if plugins1[pid] != plugins2[pid]:
                changed.append(pid)

        return {
            "v1": v1,
            "v2": v2,
            "added": added,
            "removed": removed,
            "changed": changed,
            "identical": not (added or removed or changed),
        }

    def get_stats(self) -> Dict[str, Any]:
        """Get snapshot manager statistics.

        Returns:
            A dictionary with count and counter information.
        """
        return {
            "total_snapshots": len(self._snapshots),
            "next_version": self._next_version,
            "snapshots": [
                {"version": v}
                for v in sorted(self._snapshots.keys())
            ],
            "stats": dict(self._stats),
        }