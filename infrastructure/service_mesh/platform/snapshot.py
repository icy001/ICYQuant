"""Mesh Snapshot for the Service Mesh Platform.

Provides ``MeshSnapshot`` for exporting mesh topology, policies,
certificates, routes, and runtime state for disaster recovery,
rollback, debugging, and drill exercises.
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from .telemetry import PlatformTelemetry
from .metrics import PlatformMetrics

logger = logging.getLogger(__name__)


class SnapshotType(str, Enum):
    """Type of snapshot."""

    FULL = "full"
    INCREMENTAL = "incremental"
    CONFIGURATION = "configuration"
    POLICY = "policy"
    ROUTES = "routes"
    CERTIFICATES = "certificates"


class SnapshotRecord:
    """Record of a mesh snapshot."""

    def __init__(
        self,
        snapshot_id: str,
        snapshot_type: SnapshotType,
    ) -> None:
        self.snapshot_id = snapshot_id
        self.snapshot_type = snapshot_type
        self.created_at = datetime.utcnow()
        self.completed_at: Optional[datetime] = None
        self.size_bytes = 0
        self._data: Dict[str, Any] = {}

    def set_data(self, key: str, value: Any) -> None:
        self._data[key] = value

    def get_data(self) -> Any:
        return self._data

    def finalize(self) -> None:
        self.completed_at = datetime.utcnow()
        data_str = json.dumps(self._data, default=str)
        self.size_bytes = len(data_str.encode("utf-8"))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "type": self.snapshot_type.value,
            "created_at": self.created_at.isoformat(),
            "completed_at": (
                self.completed_at.isoformat()
                if self.completed_at
                else None
            ),
            "size_bytes": self.size_bytes,
            "data_keys": list(self._data.keys()),
        }

    def export(self) -> Dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "type": self.snapshot_type.value,
            "created_at": self.created_at.isoformat(),
            "data": self._data,
        }


class MeshSnapshot:
    """Manages mesh platform snapshots."""

    def __init__(
        self,
        telemetry: Optional[PlatformTelemetry] = None,
        metrics: Optional[PlatformMetrics] = None,
    ) -> None:
        self._lock = threading.RLock()
        self._telemetry = telemetry or PlatformTelemetry()
        self._metrics = metrics or PlatformMetrics()
        self._snapshots: Dict[str, SnapshotRecord] = {}
        self._type_index: Dict[str, List[str]] = {}
        self._next_id = 0
        self._max_snapshots = 100
        self._collectors: Dict[str, Any] = {}

    def _generate_id(self) -> str:
        self._next_id += 1
        return f"snap-{int(time.monotonic())}-{self._next_id}"

    def register_collector(
        self,
        name: str,
        collector: Any,
    ) -> None:
        self._collectors[name] = collector

    def create_snapshot(
        self,
        snapshot_type: SnapshotType = SnapshotType.FULL,
        custom_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create a mesh snapshot."""
        snapshot_id = self._generate_id()
        record = SnapshotRecord(snapshot_id, snapshot_type)

        # Collect data based on type
        data = self._collect_snapshot_data(snapshot_type)

        if custom_data:
            data.update(custom_data)

        # Add metadata
        data["metadata"] = {
            "snapshot_id": snapshot_id,
            "type": snapshot_type.value,
            "created_at": datetime.utcnow().isoformat(),
            "collectors_used": list(self._collectors.keys()),
        }

        record.set_data("data", data)
        record.finalize()

        self._add_record(record)

        self._metrics.increment_snapshot_total(
            {"type": snapshot_type.value}
        )
        self._telemetry.log_snapshot(
            "create", "completed", record.size_bytes,
            {"snapshot_id": snapshot_id,
             "type": snapshot_type.value},
        )

        logger.info(
            "Created snapshot '%s' (type=%s, size=%d bytes).",
            snapshot_id,
            snapshot_type.value,
            record.size_bytes,
        )
        return record.to_dict()

    def _collect_snapshot_data(
        self, snapshot_type: SnapshotType
    ) -> Dict[str, Any]:
        """Collect data for snapshot based on type."""
        data: Dict[str, Any] = {
            "topology": self._collect_topology(),
            "policies": self._collect_policies(),
            "routes": self._collect_routes(),
            "runtime_state": self._collect_runtime_state(),
        }

        if snapshot_type in (
            SnapshotType.FULL, SnapshotType.CERTIFICATES
        ):
            data["certificates"] = self._collect_certificates()

        if snapshot_type == SnapshotType.CONFIGURATION:
            data = {
                "configuration": self._collect_configuration(),
            }

        if snapshot_type == SnapshotType.POLICY:
            data = {
                "policies": self._collect_policies(),
            }

        if snapshot_type == SnapshotType.ROUTES:
            data = {
                "routes": self._collect_routes(),
            }

        if snapshot_type == SnapshotType.INCREMENTAL:
            data["incremental"] = True
            data["changed_at"] = datetime.utcnow().isoformat()

        return data

    def _collect_topology(self) -> Dict[str, Any]:
        return {
            "nodes": [],
            "services": [],
            "connections": [],
        }

    def _collect_policies(self) -> Dict[str, Any]:
        return {
            "traffic_policies": {},
            "security_policies": {},
            "feature_flags": {},
        }

    def _collect_routes(self) -> Dict[str, Any]:
        return {
            "virtual_services": [],
            "destination_rules": [],
        }

    def _collect_certificates(self) -> Dict[str, Any]:
        return {
            "certificates": [],
            "trust_domains": [],
        }

    def _collect_runtime_state(self) -> Dict[str, Any]:
        return {
            "running_services": [],
            "active_connections": 0,
            "load_average": 0.0,
        }

    def _collect_configuration(self) -> Dict[str, Any]:
        return {
            "global": {},
            "per_service": {},
        }

    def _add_record(self, record: SnapshotRecord) -> None:
        with self._lock:
            self._snapshots[record.snapshot_id] = record
            type_key = record.snapshot_type.value
            if type_key not in self._type_index:
                self._type_index[type_key] = []
            self._type_index[type_key].append(record.snapshot_id)

            # Enforce max snapshots
            while len(self._snapshots) > self._max_snapshots:
                oldest_id = next(iter(self._snapshots))
                self._snapshots.pop(oldest_id, None)

    def get_snapshot(self, snapshot_id: str) -> Optional[SnapshotRecord]:
        return self._snapshots.get(snapshot_id)

    def export_snapshot(self, snapshot_id: str) -> Optional[Dict[str, Any]]:
        record = self._snapshots.get(snapshot_id)
        if record:
            return record.export()
        return None

    def list_snapshots(
        self,
        snapshot_type: Optional[SnapshotType] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        snapshots = list(self._snapshots.values())
        if snapshot_type:
            snapshots = [
                s for s in snapshots
                if s.snapshot_type == snapshot_type
            ]
        return [s.to_dict() for s in snapshots[-limit:]]

    def delete_snapshot(self, snapshot_id: str) -> Dict[str, Any]:
        with self._lock:
            removed = self._snapshots.pop(snapshot_id, None)
            if removed:
                type_key = removed.snapshot_type.value
                if type_key in self._type_index:
                    ids = self._type_index[type_key]
                    if snapshot_id in ids:
                        ids.remove(snapshot_id)
                return {"success": True}
            return {"success": False, "error": "Snapshot not found"}

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "total_snapshots": len(self._snapshots),
                "by_type": {
                    k: len(v)
                    for k, v in self._type_index.items()
                },
                "total_size_bytes": sum(
                    s.size_bytes
                    for s in self._snapshots.values()
                ),
                "max_snapshots": self._max_snapshots,
            }

    def __repr__(self) -> str:
        with self._lock:
            return (
                f"MeshSnapshot(snapshots={len(self._snapshots)})"
            )
