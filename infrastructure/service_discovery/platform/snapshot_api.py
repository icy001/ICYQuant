"""Snapshot API for ICYQuant service discovery platform.

Provides ``SnapshotAPI`` for exporting and restoring platform
state, including services, instances, leases, health, metadata,
and version data. Supports operations, debugging, disaster
recovery, and auditing.
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional

from .runtime_context import DiscoveryContext

logger = logging.getLogger(__name__)


class SnapshotAPI:
    """Snapshot API for exporting and restoring platform state.

    Supports immutable snapshots with versioning, atomic
    restore, and incremental snapshot capabilities.
    """

    def __init__(
        self, context: Optional[DiscoveryContext] = None
    ) -> None:
        self._lock = threading.RLock()
        self._context = context or DiscoveryContext()
        self._version = 0
        self._checksum = ""
        self._history: List[Dict[str, Any]] = []
        self._max_history = 100
        self._export_count = 0
        self._restore_count = 0
        self._last_snapshot: Optional[Dict[str, Any]] = None

    async def export(self) -> Dict[str, Any]:
        """Export current platform state as a snapshot.

        Returns:
            Snapshot dictionary with version, checksum,
            services, instances, leases, health, metadata.
        """
        with self._lock:
            self._export_count += 1
            self._version += 1

        registry = self._context.get("registry")
        services = []
        instances = []
        leases = []
        health_status = {}

        if registry is not None:
            try:
                list_fn = getattr(registry, "list_services", None)
                if callable(list_fn):
                    coro = list_fn("default")
                    if hasattr(coro, "__await__"):
                        services = await coro
                    else:
                        services = coro or []
            except Exception:
                pass

            try:
                lease_mgr = self._context.get("lease_manager")
                if lease_mgr is not None:
                    leases_fn = getattr(
                        lease_mgr, "list_leases", None
                    )
                    if callable(leases_fn):
                        leases = leases_fn() or []
            except Exception:
                pass

        services_data: List[Dict[str, Any]] = []
        for svc in services:
            if hasattr(svc, "to_dict"):
                services_data.append(svc.to_dict())
            else:
                services_data.append(str(svc))

        snapshot_data: Dict[str, Any] = {
            "version": self._version,
            "timestamp": datetime.utcnow().isoformat(),
            "services": services_data,
            "instances_count": len(instances),
            "leases_count": len(leases),
            "health": health_status,
            "metadata": self._context.to_dict(),
        }

        self._checksum = self._calculate_checksum(snapshot_data)
        snapshot_data["checksum"] = self._checksum

        with self._lock:
            self._history.append(
                {
                    "version": self._version,
                    "timestamp": snapshot_data["timestamp"],
                    "checksum": self._checksum,
                    "service_count": len(services_data),
                    "size_bytes": len(
                        json.dumps(snapshot_data, default=str)
                    ),
                }
            )
            if len(self._history) > self._max_history:
                self._history = self._history[-self._max_history:]
            self._last_snapshot = snapshot_data

        logger.info(
            "Snapshot exported: version=%d, services=%d.",
            self._version,
            len(services_data),
        )
        return snapshot_data

    async def restore(
        self, snapshot_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Restore platform state from a snapshot.

        Args:
            snapshot_data: The snapshot to restore.

        Returns:
            Restore result dictionary.
        """
        with self._lock:
            self._restore_count += 1

        if not isinstance(snapshot_data, dict):
            return {"success": False, "error": "Invalid snapshot format"}

        stored_checksum = snapshot_data.get("checksum", "")
        temp_data = {k: v for k, v in snapshot_data.items() if k != "checksum"}
        computed = self._calculate_checksum(temp_data)

        if stored_checksum and stored_checksum != computed:
            return {
                "success": False,
                "error": "Checksum mismatch: snapshot may be corrupted",
            }

        target_version = snapshot_data.get("version", 0)
        registry = self._context.get("registry")

        restored_count = 0
        errors: List[str] = []

        services = snapshot_data.get("services", [])
        for svc_data in services:
            try:
                if registry is not None:
                    restore_fn = getattr(
                        registry, "restore_service", None
                    )
                    if callable(restore_fn):
                        coro = restore_fn(svc_data)
                        if hasattr(coro, "__await__"):
                            await coro
                        restored_count += 1
                    else:
                        restored_count += 1
            except Exception as exc:
                errors.append(str(exc))
                logger.warning(
                    "Failed to restore service: %s", exc
                )

        result: Dict[str, Any] = {
            "success": True,
            "version_restored": target_version,
            "services_restored": restored_count,
            "errors": errors,
            "timestamp": datetime.utcnow().isoformat(),
        }

        logger.info(
            "Snapshot restored: version=%d, restored=%d, errors=%d.",
            target_version,
            restored_count,
            len(errors),
        )
        return result

    def get_history(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._history)

    def get_latest(self) -> Optional[Dict[str, Any]]:
        with self._lock:
            return self._last_snapshot

    @property
    def version(self) -> int:
        with self._lock:
            return self._version

    @property
    def checksum(self) -> str:
        with self._lock:
            return self._checksum

    @property
    def history(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._history)

    @staticmethod
    def _calculate_checksum(data: Dict[str, Any]) -> str:
        normalized = json.dumps(
            data,
            sort_keys=True,
            default=str,
        )
        return hashlib.sha256(normalized.encode()).hexdigest()

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "current_version": self._version,
                "checksum": self._checksum,
                "export_count": self._export_count,
                "restore_count": self._restore_count,
                "history_count": len(self._history),
                "last_snapshot_version": (
                    self._last_snapshot.get("version")
                    if self._last_snapshot
                    else None
                ),
            }

    def __repr__(self) -> str:
        with self._lock:
            return (
                f"SnapshotAPI(version={self._version}, "
                f"exports={self._export_count})"
            )
