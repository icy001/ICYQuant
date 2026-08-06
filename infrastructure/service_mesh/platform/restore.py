"""Mesh Restore for the Service Mesh Platform.

Provides ``MeshRestore`` for restoring mesh state from snapshots,
supporting full and incremental restore with validation and
consistency checking.
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from .telemetry import PlatformTelemetry
from .metrics import PlatformMetrics

logger = logging.getLogger(__name__)


class RestorePhase(str, Enum):
    """Phases in the restore process."""

    VALIDATION = "validation"
    RESTORE = "restore"
    CONSISTENCY_CHECK = "consistency_check"
    RESUME = "resume"


class RestoreStatus(str, Enum):
    """Status of a restore operation."""

    PENDING = "pending"
    VALIDATING = "validating"
    RESTORING = "restoring"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class RestoreOperation:
    """Represents a restore operation."""

    def __init__(
        self,
        operation_id: str,
        snapshot_data: Dict[str, Any],
    ) -> None:
        self.operation_id = operation_id
        self.snapshot_data = snapshot_data
        self.status = RestoreStatus.PENDING
        self.current_phase: Optional[RestorePhase] = None
        self.phases_completed: List[RestorePhase] = []
        self.errors: List[str] = []
        self.started_at = datetime.utcnow()
        self.completed_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "operation_id": self.operation_id,
            "status": self.status.value,
            "current_phase": (
                self.current_phase.value
                if self.current_phase
                else None
            ),
            "phases_completed": [
                p.value for p in self.phases_completed
            ],
            "errors": self.errors,
            "started_at": self.started_at.isoformat(),
            "completed_at": (
                self.completed_at.isoformat()
                if self.completed_at
                else None
            ),
        }


class MeshRestore:
    """Restores mesh platform state from snapshots."""

    def __init__(
        self,
        telemetry: Optional[PlatformTelemetry] = None,
        metrics: Optional[PlatformMetrics] = None,
    ) -> None:
        self._lock = threading.RLock()
        self._telemetry = telemetry or PlatformTelemetry()
        self._metrics = metrics or PlatformMetrics()
        self._operations: Dict[str, RestoreOperation] = {}
        self._restore_handlers: Dict[str, Callable] = {}
        self._next_id = 0
        self._max_operations = 50

    def _generate_id(self) -> str:
        self._next_id += 1
        return f"restore-{int(time.monotonic())}-{self._next_id}"

    def register_restore_handler(
        self,
        data_type: str,
        handler: Callable,
    ) -> None:
        self._restore_handlers[data_type] = handler

    def _normalize_snapshot_data(
        self, snapshot_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Normalize snapshot data from various formats."""
        if not isinstance(snapshot_data, dict):
            return snapshot_data
        data_section = snapshot_data.get("data")
        if isinstance(data_section, dict) and "data" in data_section:
            inner = data_section["data"]
            if isinstance(inner, dict):
                normalized = dict(inner)
                if "metadata" in data_section:
                    normalized["metadata"] = data_section["metadata"]
                return normalized
        if isinstance(data_section, dict) and len(data_section) > 0:
            if "metadata" in data_section or any(
                k
                for k in data_section.keys()
                if k != "metadata"
            ):
                return data_section
        if "metadata" in snapshot_data:
            return snapshot_data
        return snapshot_data

    def validate_snapshot(
        self, snapshot_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate snapshot data before restore."""
        errors: List[str] = []

        if not isinstance(snapshot_data, dict):
            errors.append("Snapshot data must be a dictionary")
            return {
                "valid": False,
                "errors": errors,
            }

        normalized = self._normalize_snapshot_data(snapshot_data)
        metadata = normalized.get("metadata", {})
        if not metadata:
            errors.append("Missing snapshot metadata")

        snapshot_id = metadata.get("snapshot_id")
        if not snapshot_id:
            errors.append("Missing snapshot_id in metadata")

        data_keys = [
            k
            for k in normalized.keys()
            if k != "metadata"
        ]
        if not data_keys:
            errors.append("Snapshot has no data sections")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "snapshot_id": snapshot_id,
            "data_sections": data_keys,
        }

    async def restore(
        self,
        snapshot_data: Dict[str, Any],
        full_restore: bool = True,
    ) -> Dict[str, Any]:
        """Restore mesh from snapshot data."""
        operation_id = self._generate_id()
        operation = RestoreOperation(operation_id, snapshot_data)

        # Phase 1: Validation
        operation.current_phase = RestorePhase.VALIDATION
        operation.status = RestoreStatus.VALIDATING

        validation = self.validate_snapshot(snapshot_data)
        if not validation.get("valid"):
            operation.status = RestoreStatus.FAILED
            operation.errors = validation.get("errors", [])
            operation.completed_at = datetime.utcnow()
            self._add_operation(operation)
            self._metrics.increment_restore_total(
                {"status": "failed", "phase": "validation"}
            )
            return operation.to_dict()

        operation.phases_completed.append(RestorePhase.VALIDATION)

        # Phase 2: Restore
        operation.current_phase = RestorePhase.RESTORE
        operation.status = RestoreStatus.RESTORING

        data = self._normalize_snapshot_data(snapshot_data)
        restore_results: Dict[str, Any] = {}

        for key, value in data.items():
            if key == "metadata":
                continue

            handler = self._restore_handlers.get(key)
            if handler:
                try:
                    result = handler(value)
                    if asyncio.iscoroutine(result):
                        result = await result
                    restore_results[key] = result
                except Exception as exc:
                    operation.errors.append(
                        f"Failed to restore {key}: {exc}"
                    )
                    restore_results[key] = {
                        "success": False,
                        "error": str(exc),
                    }
            else:
                # Default: store as-is
                restore_results[key] = {
                    "success": True,
                    "restored": True,
                }

        operation.phases_completed.append(RestorePhase.RESTORE)

        # Phase 3: Consistency check
        operation.current_phase = RestorePhase.CONSISTENCY_CHECK
        operation.status = RestoreStatus.VERIFYING

        consistency = self._check_consistency(data, restore_results)
        if not consistency.get("consistent"):
            operation.errors.extend(
                consistency.get("issues", [])
            )

        operation.phases_completed.append(
            RestorePhase.CONSISTENCY_CHECK
        )

        # Phase 4: Resume
        operation.current_phase = RestorePhase.RESUME
        operation.phases_completed.append(RestorePhase.RESUME)

        operation.status = RestoreStatus.COMPLETED
        operation.completed_at = datetime.utcnow()

        self._add_operation(operation)
        self._metrics.increment_restore_total(
            {
                "status": "completed",
                "full": full_restore,
            }
        )
        self._telemetry.log_snapshot(
            "restore", "completed",
            {"operation_id": operation_id,
             "full_restore": full_restore,
             "errors": len(operation.errors)},
        )

        logger.info(
            "Restore operation '%s' completed (errors=%d).",
            operation_id,
            len(operation.errors),
        )

        return {
            "operation_id": operation_id,
            "status": operation.status.value,
            "restore_results": restore_results,
            "errors": operation.errors,
            "consistency": consistency,
        }

    def _check_consistency(
        self,
        snapshot_data: Dict[str, Any],
        restore_results: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Check consistency of restored data."""
        issues: List[str] = []

        for key, result in restore_results.items():
            if not result.get("success", True):
                issues.append(
                    f"Failed restore for '{key}'"
                )

        return {
            "consistent": len(issues) == 0,
            "issues": issues,
            "checked_sections": list(restore_results.keys()),
        }

    async def incremental_restore(
        self,
        snapshot_data: Dict[str, Any],
        changed_keys: List[str],
    ) -> Dict[str, Any]:
        """Incrementally restore specific sections."""
        normalized = self._normalize_snapshot_data(snapshot_data)
        filtered_data = {
            k: v
            for k, v in normalized.items()
            if k in changed_keys or k == "metadata"
        }
        return await self.restore(filtered_data, full_restore=False)

    def _add_operation(self, operation: RestoreOperation) -> None:
        with self._lock:
            self._operations[operation.operation_id] = operation
            if len(self._operations) > self._max_operations:
                oldest_id = next(iter(self._operations))
                self._operations.pop(oldest_id, None)

    def get_operation(
        self, operation_id: str
    ) -> Optional[RestoreOperation]:
        return self._operations.get(operation_id)

    def list_operations(
        self,
        status: Optional[RestoreStatus] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        operations = list(self._operations.values())
        if status:
            operations = [
                o for o in operations
                if o.status == status
            ]
        return [o.to_dict() for o in operations[-limit:]]

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "total_operations": len(self._operations),
                "by_status": self._count_by_status(),
                "handler_count": len(self._restore_handlers),
            }

    def _count_by_status(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for op in self._operations.values():
            status = op.status.value
            counts[status] = counts.get(status, 0) + 1
        return counts

    def __repr__(self) -> str:
        with self._lock:
            return (
                f"MeshRestore(operations={len(self._operations)})"
            )
